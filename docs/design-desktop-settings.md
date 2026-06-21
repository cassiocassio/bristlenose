---
status: current
last-trued: 2026-04-30
trued-against: HEAD@first-run on 2026-04-30 (Beat 3 + 3b shipped)
---

## Changelog

- _2026-06-21_ — repointed the `degradedBody` reference from the deleted `PipelineActivityItem.swift` to `ProjectDiagnosticPopover.swift` (the failure popover was extracted there, commit `02ad258`).
- _2026-06-06_ — Corrected the eager-board §"Online behaviour" verification gate after grounding it in Apple docs + prior art: the "3× Keychain prompt cascade" is a *legacy file-based keychain* symptom (Always-Allow grant bound to the binary's code-directory hash), **not** a "dev/DerivedData artifact." We already migrated to the data-protection keychain (`8b2ef51`), which validates by Team ID and has no ACLs, so own-access-group reads don't prompt on a team-signed build. Gate narrowed from "discover whether eager is viable" → "confirm the build isn't ad-hoc." Refs: Apple TN3137, steipete/CodexBar #585. Also recorded Martin's "no rung-3/billing call on open" decision and the open "green = valid vs runnable?" offline-rendering question (pending ponder). The stale `desktop/CLAUDE.md` Debug-signing note was reconciled to the data-protection model in the same pass.
- _2026-06-06_ — Added §"Provider status lifecycle (planned)" — the truthful-effort-free-board design that supersedes the parked NWPathMonitor-toast coverage gap. Captures the four-rung cost ladder (in-memory / Keychain / network-auth / real-work-call), the online optimistic-from-cache + silent-background-reconfirm policy (kills the lazy-load "dashboard of lies"), the offline three-bucket model ("worked before" vs "never configured" vs "not set up"), the 402-masked-as-green fix (split `.unavailable` into observation-failed vs observed-a-negative), the refocus-recheck for credit top-ups, and the shared `probe(provider, model)` rung-3 unit (key-entry / refocus / `scripts/llm-weather.py`). Also records the activation-no-op root cause (lazy status → radio guard bails) and the `overlayPreferences` model-without-provider leak fix. Section is design-forward (not yet shipped) — clearly delineated from the shipped Beat 3/3b flow above. Anchors: `BristlenoseShared.swift` `overlayPreferences`, `LLMSettingsView.swift` `applyPresenceAndCache`/`refreshStatuses`/`kickOffValidation`, `LLMValidator.swift` `classify`/`buildRequest`.
- _2026-04-30_ — Beat 3b + post-merge review fixes reconciled. Ollama URL hardwired to `localhost:11434/v1` in the desktop GUI (commit `dbd54ec`); editable TextField removed and replaced with static read-only display. CLI/CI override via parent-process `BRISTLENOSE_LOCAL_URL` env var only (`ServeManager.swift:351-357`, `BristlenoseShared.swift:122-127`). `localURL` UserDefaults key dropped from the env-injection table — no longer touched by the GUI. Added §"Validation invariants" subsection capturing the "presence-and-cache reader never sets `.checking`" contract that prevents radio-toggle stranded-spinner regressions, and the Azure focus-blur revalidation pattern that deliberately replaced per-keystroke validation. AIConsent + OllamaSetupSheet first-run flow cross-referenced (canonical home is the parked `design-first-run-flow.md` — see 100days §3 Should). Anchors: `LLMSettingsView.swift:331-348`, `LLMSettingsView.swift:524-536`, `LLMSettingsView.swift:629-637`.
- _2026-04-29_ — Beat 3 reconciled: round-trip credential validation now shipped via new `LLMValidator.swift`. ProviderStatus table augmented to cover Azure 404 → `.invalid` and Anthropic forward-compat (any 4xx ≠ 401/403/402/429 → `.online`, robust against haiku-model deprecation). New §"Validation flow" subsection documents the verdict cache (SHA256-prefix keyed, UserDefaults), 60s TTL gate, offline survival via cache fallback on transient `.unavailable`, `.checking` rendered as `ProgressView` (Mail-style spinner), animated dot transitions, and the "Last verified Xm ago" line. Tightened Ollama line to specify HTTP probe target (`<url>/api/tags`). Anchors: `desktop/Bristlenose/Bristlenose/LLMValidator.swift`, `desktop/Bristlenose/Bristlenose/LLMSettingsView.swift`, `desktop/Bristlenose/Bristlenose/LLMProvider.swift`.
- _2026-04-21_ — trued up, minor additions: noted Ollama status derives from URL reachability (no key-injection); noted `overlayPreferences` don't-override-default guard (only explicitly-set values get emitted); noted `KeychainStore` protocol + `InMemoryKeychain` test shim; promoted threat-model rationale (env-vars vs keychain-access-groups residual-risk delta) from `ServeManager.swift:366-371` comment; added cross-ref to `design-settings-ui.md` for the serve-mode web-UI path (complement, not competitor) and `design-keychain.md` §Desktop credential path.
- _2026-04-20_ — trued in C3 closeout pass; structural accuracy confirmed against `SettingsView.swift`, `ServeManager.swift`, `LLMProvider.swift`.

# Desktop Settings Window (Cmd+,)

Apple canonical `Settings` scene with 3 icon tabs. Constant width (660pt) across all tabs, height animates to fit content. Working context lives in `desktop/CLAUDE.md`. Related: `design-settings-ui.md` (serve-mode web UI — complementary, not competing: web UI is the CLI/serve path; this is the embedded-alpha path), `design-keychain.md` §Desktop (sandboxed) credential path (canonical home for the Swift→env-var→Python architecture).

## Tab 1: Appearance (paintbrush)

Theme radio group (auto/light/dark) + a hint paragraph pointing users to System Settings → Apps → Bristlenose for language. `@AppStorage("appearance")` drives `.preferredColorScheme` on both the main window and Settings window. Appearance is also synced to the web layer via `BridgeHandler.syncAppearance()` on `ready` — native wins, web Settings modal hides its appearance picker in embedded mode.

**No in-app language picker.** macOS already provides per-app language switching at System Settings → General → Language & Region → Apps → Bristlenose, so we delegate. `INFOPLIST_KEY_UIPrefersShowingLanguageSettings = YES` (in `project.pbxproj`) forces that section to appear even for users with only one preferred language configured globally. `I18n.swift` reads `Bundle.preferredLocalizations(from:forPreferences:)` on every launch to honour the user's choice. Canonical design: `docs/design-locale-negotiation.md`. The web Settings modal in CLI serve mode keeps its language picker — browsers have no per-site override, so the in-app control is the only escape hatch there.

## Tab 2: LLM (brain) — Mail Accounts pattern

Left sidebar list of 5 pre-populated providers (Claude, ChatGPT, Gemini, Azure, Ollama) with two orthogonal indicators per row:
- **Radio/checkmark** — which provider is active (user choice, `@AppStorage("activeProvider")`)
- **Status dot** — whether the provider is configured (green "Online" / grey "Not set up" / red "Invalid" / orange "Unavailable")

Right detail pane shows the selected provider's settings: API key (`SecureField` → Keychain via `KeychainHelper`), model picker (per-provider known models + "Custom…"), temperature slider, concurrency slider. Azure adds endpoint/deployment/version fields. Ollama shows a **read-only** static display of the URL (`localhost:11434`) — the field is hardwired in the desktop GUI as a trust-boundary closure (commit `dbd54ec`, 30 Apr 2026): a social-engineered user pasting an attacker URL would silently exfiltrate transcripts over plain HTTP, contradicting the "transcripts stay on your Mac" claim. Status derives from an HTTP probe to `<hardwired-url>/api/tags`, parsing the models list to distinguish "not running" from "running but no models pulled"; see `LLMValidator.probeOllama`. CLI users and CI keep the override path via the `BRISTLENOSE_LOCAL_URL` env var (parent-process only — see §Preferences below).

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
| Ollama URL | *(parent process env only)* | `BRISTLENOSE_LOCAL_URL` |
| Appearance | `appearance` | *(bridge, not env)* |

> **Note on `BRISTLENOSE_LOCAL_URL`:** the desktop GUI hardwires the Ollama URL (no editable field). `overlayPreferences` therefore reads only the **parent process environment** for `BRISTLENOSE_LOCAL_URL` and forwards it to the sidecar if set — there's no UserDefaults round-trip. CLI users and CI keep the override path; desktop alpha users are locked to localhost. See `ServeManager.swift:351-357`, `BristlenoseShared.swift:122-127`, and `LLMSettingsView.swift` `hardwiredOllamaURL` constant.
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

**Coverage gap (parked → superseded).** `LLMValidator` runs only when
Settings is open or on Save. There's no app-wide background revalidation —
a key rotated server-side while the user is offline isn't detected until
they next open Settings. The original follow-up proposed `NWPathMonitor` +
a **toast** on cached-`.ok` → fresh-`.invalid` transitions. **The toast is
withdrawn** (toasts are an attention-theft pattern — see project memory);
the replacement design is inline status that's eagerly truthful on open
plus a refocus-recheck, captured in §"Provider status lifecycle (planned)"
below. `NWPathMonitor` survives as the reachability gate in that design.

## Validation invariants

These contracts protect against regressions seen during Beat 3b QA:

**`applyPresenceAndCache` never sets `.checking`.** Only `kickOffValidation`
does — and it sets `.checking` synchronously before the await. The
presence-and-cache reader is purely a "show last-known state" function. If
it ever wrote `.checking` itself, any code path that calls `refreshStatuses`
without following up with `kickOffValidation` (radio-toggle, active-toggle)
would strand the provider in a forever-spinner. Masked for cloud providers
by the verdict cache; immediately surfaced for Ollama because Ollama doesn't
use the cache. Comment block at `LLMSettingsView.swift:629-637` is the
load-bearing record.

**Azure revalidation fires on focus blur, not per-keystroke.** Typing
`https://my-instance.openai.azure.com` would otherwise issue ~30 validation
requests, each one a billed Azure call plus a rate-limit hit. `revalidateAzure()`
(`LLMSettingsView.swift:524-536`) is wired through `@FocusState` for the
endpoint and `apiVersion` fields with `onSubmit` (Enter) as the secondary
trigger. Per-keystroke `.onChange` is retained only for the prefs notification
(cheap UI signal, no network round-trip).

**Consent recorded BEFORE prefs notification on Ollama setup.** When the
"Use Ollama Instead" path completes (`AIConsentView.swift:60-69`), `recordConsent`
runs first, then `activeProvider` is set, then `bristlenosePrefsChanged`
posts. If the order were reversed, a prefs-change-driven serve start could
fire pre-consent. Consent gate downstream still catches it — but the
ordering is deliberate, not incidental.

Status is orthogonal to active selection. Providers don't expose balance, free-tier, or trial status via API — we report only what we can detect.

## Provider status lifecycle (planned)

> **Status: design-forward, not yet shipped.** Everything above this heading
> describes the shipped Beat 3/3b behaviour. This section is the agreed target
> the next implementation phases move toward. Where it contradicts shipped
> behaviour (the lazy-load board, the activation guard, 402 handling), the
> shipped behaviour is the *defect* and this section is the *intent*.

### Product principle: the board is truthful and effortless

The LLM tab reads as a **dashboard of status lights**, so it must *be* one.
Two failures, observed in alpha QA, are non-negotiably wrong:

1. **A board that lies** — lights that are unlit because the app was lazy, not
   because the state is unknown. The user reads the board as truth; it must be.
2. **"Rocks to look under"** — making the user click each row to make its light
   come on. That hands the app's own job back to the user.

The user's correct expectations: **with a network, a live, real-time view that
keeps itself honest with zero clicks; history leveraged so a previously-good
provider is silently and magically reconfirmed.** The *only* genuinely
ambiguous case is no-network — and even there, local history distinguishes
"worked before" from "never configured." **The user never pays, sees, or
manages the cost of keeping the board honest.**

### The cost ladder (backstage only)

These "costs" are the *implementation's* to absorb and hide — never a
user-facing concept. They exist to explain *which technique runs when*.

| Rung | Operation | Cost | Proves | Cannot tell us |
|------|-----------|------|--------|----------------|
| **0. In-memory** | read cached verdict (`verdictStore`) | free, instant, offline-ok | what we concluded last time | anything current |
| **1. Local API** | Keychain `SecItemCopyMatching` | a syscall; real cost = **prompt risk in unsigned/dev builds**; offline-ok | a credential *exists* (+ value to hash) | is it valid? endpoint up? credit? model real? |
| **2. Network auth** | minimal auth round-trip (`LLMValidator.buildRequest`) | ~1s, needs net, < $0.0001 | endpoint *reachable* + key *authenticates* (200 vs 401) | credit? model valid? |
| **3. Real work call** | structured `analyze()` against a fixture | fractions of a cent, needs net | credit OK (402 vs 200) + model exists (vs 404) + model does structured output → *a real run will succeed* | — this **is** ground truth |

**Rung 2→3 is a wall the providers built, not one we can engineer around.**
They check auth (401) *before* billing (402) — so a 200 on rung 2 is
structurally incapable of reporting credit. Note the asymmetry in the shipped
rung-2 pings: Claude uses `POST /v1/messages max_tokens=1` (brushes billing →
*would* catch a 402), while ChatGPT/Gemini/Azure use `GET …/models` (pure auth
→ a 200 says nothing about credit). So a green light honestly means **"set up ·
key valid · reachable,"** not **"will produce work."** Copy must not over-claim.

### Online behaviour — live, self-reconfirming, zero clicks

On Settings open *with* a network:

1. **Paint instantly from history (rung 0).** Every configured provider shows
   its last-known verdict immediately — no spinner wall. This is the
   "leverage history" the user expects.
2. **Silently reconfirm in the background (rung 2) for *all* rows, not just
   selected+active.** Lights settle into present-tense truth over ~1s. This is
   the "silently and magically reconfirmed" behaviour.

This **replaces the lazy-load policy** (which only read selected+active and
left every other row grey-by-laziness). The lazy-load's sole justification was
the "3× Keychain prompt cascade" (sandbox walk #7) — which Apple's documentation
and prior art say a properly-signed build **won't** exhibit. The cascade is a
*legacy file-based keychain* symptom: that keychain binds each "Always Allow"
grant to the binary's **code-directory hash**, so any rebuild or re-sign
invalidates every grant and re-prompts (Apple TN3137; steipete/CodexBar #585 hit
and fixed this exact thing). We already migrated off it (2 Jun, `8b2ef51`):
`KeychainHelper` passes `kSecUseDataProtectionKeychain` on every operation, with
a team-scoped `keychain-access-groups` entitlement
(`$(AppIdentifierPrefix)app.bristlenose`) and no biometric `SecAccessControl`.
The data-protection keychain validates by **Team ID, not binary hash**, has no
ACLs, and does **not** prompt an app reading its *own* access-group items — so
eager all-providers reads are expected to be silent on any team-signed build.

**Verification gate (narrowed):** the question is no longer "is eager viable" —
the documented default is *no prompts*. It is "**is the running build ad-hoc?**"
Ad-hoc (`None` + `Sign to Run Locally`) has an empty `$(AppIdentifierPrefix)`,
which breaks the access group and falls back to the legacy keychain → prompts.
Confirm the build is team-signed (`Z56GZVA2QB`); TestFlight/MAS builds always
are. **Fallback if a prompt ever appears on a signed build** (the surprise
case, now requiring explanation rather than expected): render the rung-0 cache
for all rows (it lives in UserDefaults, not Keychain) and defer the Keychain
read.

**Do not over-poll billing on open.** Upgrading the open-time reconfirm to a
rung-3 (billing-touching) call for every provider buys marginal extra truth
(credit) at the cost of token spend, rate-limit risk, and "why is it calling
Anthropic every time I open Settings." Credit only *bites* at two moments, both
handled truthfully there: refocus-after-paying and the Run itself. Green =
"valid & reachable" is honest enough provided the Run is never gated on a stale
light.

> **Decided (2026-06-06, Martin):** no rung-3/billing call on Settings-open.
> Open-time reconfirm stays at rung 2 ("is the endpoint alive + does the key
> authenticate"). Simpler is better at this stage; we don't spend even sub-cent
> amounts just to light up lights with marginally more certainty. Credit truth
> is bought only at refocus-after-paying and at Run.

### Status indicator vocabulary — decided (2026-06-06, Martin)

The status light is **colour + the text label, nothing else**. No per-state
glyphs. Two independent reasons, either sufficient:

1. **Every glyph is a "what does that symbol mean?" tax.** The label already
   says "Online" / "Out of credit" / "Invalid key" — a glyph adds a thing to
   parse, not information. ("Absence is information — no glyph for the normal
   case.")
2. **Two ticks, one row.** The sidebar row *already* carries a **blue**
   `checkmark.circle.fill` for the *active/selected* provider. A **green**
   status checkmark on `.online` would put two ticks on the same line — blue
   "selected" beside green "OK" — a real collision of meanings. So `.online`
   stays a plain green dot. (This kills the glyph-every-state option outright,
   independent of reason 1.)

Accessibility: for a colour-blind user the **text label** carries the meaning
(the two ambers read "Unavailable" vs "Out of credit"). This is an accepted
**deferral** for TF/alpha — the one tracked a11y debt — not a resolution. If a
shape-per-state is ever added, it must dodge the blue/green tick collision above.

**No "settling" indicator** during background reconfirm ("too cute"). The dot
just changes if the verdict changes; the silent reconfirm is the whole point of
the eager board.

**`.checking` (the spinner) stays — and earns its keep at exactly one moment:
first validation on key paste.** Key entry is the high-anxiety step (a trailing
space, a fat-fingered paste — everyone has the story), so the user wants live
"Checking…" feedback *there*. Hence the split in `kickOffValidation`:
`silent: false` on the paste/`saveAPIKey` path (spinner shown — reassurance),
`silent: true` on background reconfirm of an already-cached provider (no spinner
wall).

### Offline behaviour — the only ambiguous case; three buckets

> **Decided (2026-06-07, Martin): leave as shipped for TF — no grey-when-offline.**
> The board keeps its last-known colour when the network drops: **green stays
> green, red stays red** (already the shipped behaviour — `resolveStatus` defers a
> transient `.unavailable` to the cached verdict). The three-bucket grey model
> below is **deferred, not built** — kept as the record of the reasoning, not the
> plan of record. Two load-bearing reasons, both Martin's:
>
> 1. **Don't diverge text from colour, and don't hide the truth.** If the label
>    says "Invalid key" the dot must stay red — greying it offline would both
>    split text-from-colour *and* hide the important fact that the key was invalid
>    last time we tried. That's worse than a slightly-stale green.
> 2. **Bristlenose is a Mac app; no-network is a normal ambient state.** Verbatim:
>    *"apple mail just doesn't care — it's a mac app on your mac and the outbox
>    just has 1 queued mail that can't go so it sits there… the lack of internet
>    is a normal state for a mac app, it's on your local device, it will send when
>    it gets network. that's bn.app. gmail is a bit more needy, and has a global 'I
>    would be happier with internet' but it doesn't change the state of the detailed
>    preference pane based on no network. for TF we are fine."* A global no-network
>    condition isn't worth dramatising per-provider: the lights report **credential
>    validity** (last-known truth); the transient "couldn't reach it just now" rides
>    as a hover caption, not a colour change.

With no network we cannot reconfirm, but local state (rung 0/1) still
distinguishes a track record from its absence. Render three buckets, not the
shipped green-or-grey collapse:

| Offline state | Local signal | Render |
|---------------|--------------|--------|
| **Worked before** | cached `.ok` exists | confident-but-dimmed: *"ready · last confirmed Tue · offline"* — history honoured, **not** a live green that implies "runnable now" |
| **Never successfully configured** | key present, no successful verdict ever (e.g. pasted while offline) | neutral: *"set up — never confirmed"* |
| **Not set up** | no key | grey *"not set up"* |
| **Known bad** | cached `.invalid` (real 401) | red, sticky — survives offline |

Connectivity is a **caption on the neutral ladder, never its own colour**
(colour belongs to credential validity). Greying-out-on-offline is *wrong* — it
discards a true fact (the key is good) to express a different one (unreachable
now); a caption carries the latter without destroying the former.

#### Resolved (2026-06-07) — green = *validity*, kept as shipped (see Decided box above). Original analysis retained:

Martin challenges the "confident-but-dimmed **green** when offline + cached `.ok`"
row above. The crux is what the colour channel *means*:

- **Validity reading (table above):** colour = credential validity, which is
  network-independent. A good key is a good key offline → stays green, caption
  notes unreachability. Doesn't discard the true fact.
- **Runnability reading (Martin's lean):** green = "I can run *now*." A cloud
  provider offline can't run now, so green over-claims → render **grey**
  ("ready · last confirmed Tue · offline"), reserving green for genuinely-
  runnable. **Local models (Ollama) are the exception** — network-independent,
  so they *stay green* offline.

Note the asymmetry Martin draws, and it's deliberate: **red survives offline**
(a known-`.invalid` key won't become valid by reconnecting — greying it would
imply "flip the wifi and it might go green," which is the lie), while **green
does not** survive offline for cloud (can't claim runnable). That puts two
different questions on one colour channel — green answers "runnable now," red
answers "credential valid." Coherent for users ("green = go"), but it breaks the
single-axis "colour = validity" rule the table above asserts. The purist counter
(raised and noted): *no network = make no claims*, which would grey everything
unconfirmable — but that throws away useful local truth (the red, and the track
record). **Resolution pending Martin's ponder.**

Two sub-decisions ride on it:

1. **`no key` glyph.** Today grey. Martin: maybe a **hollow/open circle** (or
   nothing) instead — so "never set up" is visually distinct from "set up but
   unconfirmed/offline," which would *also* be grey under the runnability
   reading. (Cf. project memory "Absence is information — no glyph for the
   normal case": an empty slot arguably *is* the normal/empty case.) If both
   "no key" and "cached-ok-offline" are grey dots, the caption is the only
   differentiator — the has-key breadcrumb (Finding 18) becomes load-bearing.
2. **`key + no cache`** = a credential exists (rung-1 read found a value) but no
   verdict was ever recorded — e.g. key pasted while offline, or written by the
   Python CLI and never validated by the Swift side, or cache evicted. Renders
   as the "set up — never confirmed" bucket: grey, distinct from both "no key"
   (nothing in Keychain) and "cached `.ok`" (validated before). It means
   *"we have a key but have never seen it work."*

### Credit / 402 — fix the masking, then re-check at the right moment

**Bug to fix:** out-of-credit (402) currently maps to `.unavailable`, and the
offline-survival rule (`cache wins on .unavailable`) promotes it back to green.
A credit-exhausted provider shows green while runs fail on quota. The fix is to
**split `.unavailable` by provenance:**

- **Observation *failed*** (timeout / no network / can't reach) → trust the
  cache; green stays green. ✅ (correct today)
- **Observation *succeeded* and reported a negative** (402 out of credit) →
  **show it** (amber "top up · re-check"); do *not* fall back to stale green.
  402 is a fresh true fact, not a failed observation. (429 rate-limit is
  borderline — self-clears in a minute — so masking it behind cache-green is
  defensible; 402 is not.)

**Top-up detection is fundamentally not free** (rung 3, see the wall above), so
don't chase a free signal. Fire the unavoidable sub-cent re-check at the
**natural moment**: `NSApplication.didBecomeActive` → re-check **only**
providers currently in a transient-failure state, **and** only if their cache
is stale (TTL debounce). Pay at the provider's console → click back to
Bristlenose → the amber row silently goes green. Plus a manual "Re-check"
control as the explicit fallback. **The Run is never gated on a stale light** —
if the user has paid and hits Run, it works; the light is a hint, the run is
truth.

**Known limitation — cached green is *network-validity*, not *credit-confirmed*.**
You cannot observe a 402 you never received: if an account runs out of credit
while the user is **offline**, every reconfirm times out, the 402 is never seen,
and the cache stays `.ok` → the row shows green and is activatable, yet runs will
fail on quota. This is a logical limit of credit-detection-requires-network, not
a defect, and it's the backstop, not the front line: the now-named run-time quota
message ("Claude is out of credits…") surfaces it clearly at Run. We accept it
rather than chase a free offline credit signal that doesn't exist. (How a cached
`.ok` *renders* while offline — confident green vs dimmed — is the open
green-vs-runnable question above; this limitation is one input to it.)

### Activation must act on truth, not on a lazily-empty status

**Root-cause record (Defect L):** the radio-activation guard
(`guard statusFor(provider).isConfigured else { return }`) and the
`.disabled(!isConfigured && …)` modifier silently no-op when the target
provider's status is `.notSetUp` — which, under lazy-load, it always is until
the user clicks into the row. So clicking a fresh provider's radio first does
nothing and `activeProvider` never persists → runs hit the previously-active
provider. **This is the same lazy-status defect as the "dashboard of lies."**
Making the board eagerly truthful (online section above) gives the guard a real
status to act on and fixes activation as a side-effect — *one change, two
payoffs.* For a provider whose status is still cold at click time, the radio
should **load-then-activate** (run presence-and-cache for that provider on
click, activate once it resolves `.online`), never swallow the click.

### `overlayPreferences` — never inject a model without a provider

**Root-cause record (Defect M, fixed):** the env overlay had an `else if` arm
that injected the bare global `llmModel` key when `activeProvider` was unset —
so Python fell back to its *default* provider (anthropic) but ran it against
whatever model the global key last held (e.g. `gpt-4o` from a prior ChatGPT
session), producing a cross-provider 404 (`model: gpt-4o` rejected by
Anthropic). **Invariant:** only inject `BRISTLENOSE_LLM_MODEL` when
`BRISTLENOSE_LLM_PROVIDER` is also set; when no provider is active, inject
neither and let Python default both coherently. The global `llmModel` key is a
footgun — it tracks the active provider's model only while `syncGlobalModel`
runs; spawning off it after a provider revert produces a mismatch. Prefer the
per-provider `llmModel_<provider>` keys as the source of truth.

### The rung-3 probe is one reusable unit

Key-entry validation, refocus-recheck, and the maintainer "weather station"
(`scripts/llm-weather.py` — provider × every-known-model sweep, see
`docs/design-llm-weather.md` if/when written) are **the same operation**:
`probe(provider, model) → ok / 404-unknown-model / 402-no-credit / auth /
schema-malformed / unreachable`. Build it **once** as a reusable unit; call it
from all three sites. Key-entry currently does *not* do rung 3 (it pings a
fixed endpoint/model, not the chosen model) — so a typo'd-but-dead model name
isn't caught at entry; adding the rung-3 probe at key-entry is deferred but
cheap to reverse once the probe exists.

### Error copy when a run fails

- `humanSummary(for:)` returns provider-less strings ("LLM provider rejected
  the request"). Thread the active provider's display name through →
  **"Claude rejected the request."**
- `degradedBody` (`ProjectDiagnosticPopover.swift`) renders the captured `message`
  *and then unconditionally* appends "Detailed cause not captured." — show
  `noStructuredCause` **only when `message` is empty**. The cause *is* captured
  (event log + `last-run-failure.log`); surface the "Provider says: …" detail
  and explain a 404 plainly ("that model name isn't valid for this provider").
