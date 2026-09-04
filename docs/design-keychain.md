---
status: partial
last-trued: 2026-09-04
previous-trued: 2026-08-18
trued-against: HEAD@main on 2026-09-04 (bcdc03b9)
---

> **Truing status:** Partial — the original design (§Design Decisions, §CLI Commands) shipped and remains the canonical CLI/serve-mode credential path, with provider-list expansion (2→5). The Track C sandboxed-desktop deployment ships a different credential path — Swift reads Keychain, injects env vars; the *sidecar* never touches Keychain — in §"Desktop (sandboxed) credential path". **Since 4 Sep 2026 the two paths share one keyspace:** the app keeps a login-keychain copy of every CLI-read key and reconciles it, so a key set up in the CLI or the app is seen by both — §"One keyspace, two keychains" is the section to read first, and it supersedes any sentence elsewhere in this doc that assumes a single keychain. Inline Python source (§Module Structure) is the pre-ship plan; see `bristlenose/credentials.py` + `credentials_macos.py` + `providers.py` (`CREDENTIALS`) for current.

## Changelog

- _2026-09-04_ — **the CLI and the Mac app could not see each other's keys, and
  now can.** Measured with two items of the same name in Keychain Access — the
  app's in iCloud (data-protection keychain), the CLI's in login — and neither
  side reading the other's. New §"One keyspace, two keychains" records what
  `security` and an unentitled Security.framework caller can actually address
  (nothing of the app's), the option chosen (the app keeps a login-keychain copy
  of every key the CLI reads and reconciles the two on read), the prompt budget
  that costs, the walk that verifies it on a real Mac, and the Keychain Access
  clean-up for a machine that already carries the split. The keyspace table's
  "Read by" column is corrected for the two shared classes. `set_verified` is
  named as the house read-back helper on the Python side.
- _2026-08-18_ — trued against per-account credential storage (`8901845f`,
  `d054b3d6`). **Two claims were factually inverted, not merely stale**, and both
  are load-bearing: §5's lookup priority said *Keychain first, then env* when the
  code is the exact reverse (`config.py:702` and siblings guard on `if not
  settings.<field>`, and `credentials_macos.py`'s own docstring says "not already
  set from env vars") — which matters because the entire sandboxed-desktop design
  works *only* because the Swift-injected env var outranks Keychain, so the doc as
  written said that injection would be ignored; and §2 struck Miro through as
  "descoped from alpha" when it has shipped, under a different service name.
  §2 also gained the second axis this doc did not have: the account string is no
  longer always `bristlenose`. New §"The keyspace" table — four credential classes
  now share one frame, which is what earns a section rather than another bullet.
  `MCPTokenStore` is named for the first time, because it is the one deliberate
  **non**-synchronizable store and every blanket sync claim here needs that
  exception. Cloud-grant mechanics are cross-referenced to
  `design-cloud-import.md` §7 (canonical, trued the same day) rather than
  retold. Anchors repointed from `ServeManager.swift` to `BristlenoseShared.swift`.
  **Left open deliberately:** the log redactor matches LLM key shapes only, so
  OAuth refresh tokens and Graph bearers pass it — flagged in §Secret-leak
  defences, not silently widened.
- _2026-06-07_ — reconciled the desktop credential path to the **data-protection keychain** migration (commit `8b2ef51`, 2 Jun 2026): added a migration note (Team-ID-not-binary-hash validation, deliberate iCloud sync, no biometric ACL, host-side `keychain-access-groups`), flipped the §"Why this split" framing (the host ships access groups; the sidecar stays keychain-free), re-anchored `overlayAPIKeys` to `BristlenoseShared.swift` (moved from `ServeManager`, now active-provider-scoped at spawn time), and fixed the Gemini service name. The CLI/serve-mode `security`-CLI path below is unchanged and still canonical. Anchors: `KeychainHelper.swift` header, `BristlenoseShared.swift` `overlayAPIKeys`, Apple TN3137, steipete/CodexBar #585. (Edge-case §"Keychain sync" hedge is now superseded by the migration note but left for a deeper pass.)
- _2026-04-29_ — confirmed still current after Beat 3 (desktop SwiftUI round-trip credential validation, `LLMValidator.swift`). Beat 3 added a new validation surface in Swift Settings that reads the Keychain key briefly to authenticate against the provider's API, but does NOT change the storage or injection architecture this doc describes — the Swift→env-var→Python flow on sidecar launch is unchanged. The verdict cache (UserDefaults: SHA-256 hash prefix + status + timestamp) is opaque metadata, not secret material; threat shape unchanged. See `design-desktop-settings.md` §"Validation flow (Beat 3)" for the validator details.
- _2026-04-21_ — trued up: expanded provider list from 2 (anthropic, openai) to 5 (anthropic, openai, azure, google, miro); updated `bristlenose configure` samples to use product names (`claude`, `chatgpt`); marked Snap section as shipped via env-var fallback; added new §"Desktop (sandboxed) credential path" for the Track C Swift→env-var→Python architecture (load-bearing invariant for alpha); added §"Secret-leak defences" covering runtime log redactor + `check-logging-hygiene.sh` CI gate. Anchors: `bristlenose/credentials.py:53-58`, `bristlenose/credentials_macos.py:39-45`, `bristlenose/cli.py:1613-1727`, `desktop/Bristlenose/Bristlenose/BristlenoseShared.swift:132-180 (`childEnvironment`, called from ServeManager.swift:312),356-383,409-473`, `desktop/Bristlenose/Bristlenose/KeychainHelper.swift`, `desktop/scripts/check-logging-hygiene.sh`, commits "inject keychain api keys as env vars", "runtime log redactor for api key shapes", "tests for env injection, redactor", "CI grep gate for Swift logging hygiene". Preserved: inlined Python source in §Module Structure as pre-ship plan record.

# Keychain Integration

Secure credential storage for API keys using native system keychains.

---

## Goal

Store API keys in the macOS Keychain (and Linux Secret Service where available) instead of `.env` files. This is:

1. **More secure** — encrypted at rest, not plain text on disk
2. **More convenient** — one credential works across all projects (on a Mac that is two keychain entries since 4 Sep 2026: the app's synced one and the login copy the CLI reads — §"One keyspace, two keychains")
3. **Expected by users** — Mac users expect credentials in Keychain Access

---

## Design Decisions

### 1. Native CLI, not shim libraries

**Decision:** Use `security` CLI on macOS, `secret-tool` CLI on Linux. No `keyring` Python library.

**Rationale:** Cross-platform shim libraries (like `keyring`) provide the lowest common denominator on every platform. They don't integrate well with native tooling — entries created by `keyring` often have weird names in Keychain Access, and the abstraction leaks when things go wrong.

Instead:
- **macOS:** Shell out to `security` CLI. It's been stable for 20+ years, ships with every Mac, and entries appear properly in Keychain Access.app
- **Linux:** Shell out to `secret-tool` CLI (part of `libsecret-tools`). If Secret Service isn't available (headless servers, minimal installs), fall back to env vars with a clear message

### 2. Credential naming

**Decision:** Human-readable service names with "API Key" suffix.

**Rationale:** Users search their keychain for "anthropic" and should find something clearly labelled. Anthropic has other credentials (console password, etc.) — the "API Key" suffix disambiguates.

### The keyspace

_Added 2026-08-18. This doc was framed around one credential class and there are
now four, which is why per-account storage and the MCP token read as absences
below rather than as errors._

| Class | Service name | Account | Synced? | Read by |
|---|---|---|---|---|
| LLM provider keys | `Bristlenose {Anthropic,OpenAI,Azure,Google Gemini} API Key` | **fixed** `bristlenose` | yes — **and a login-keychain copy** (§"One keyspace, two keychains") | Swift host → env; CLI Python directly, from the login copy |
| Miro token | `Bristlenose Miro Access Token` | **fixed** `bristlenose` | yes — **and a login-keychain copy** | Swift host (`overlayMiroToken`, unconditional); the serve route via `get_credential()`, which is **store first, then env** — the opposite order from the settings pipeline in §5 |
| Miro refresh token | `Bristlenose Miro_Refresh API Key` — the *fallback* name for an unregistered key | **fixed** `bristlenose` | **login only**, and only on a CLI Mac | The serve OAuth route alone (`routes/miro.py`). **Known gap (4 Sep 2026):** not in `CREDENTIALS`, not in `KeychainHelper.serviceNames`, so the app cannot read it and the contract test cannot see it. Registering it renames the item and the `.env` key for existing users, so it is recorded here rather than changed |
| Cloud sign-ins | `Bristlenose {Microsoft Teams,Google Meet} Sign-In` | **derived** — SHA-256 of the lowercased address | yes | Swift only |
| MCP bearer | `Bristlenose MCP Token` | **derived** — SHA-256 of the project path | **no** | Swift host → sidecar env |

Three things about that table are load-bearing:

- **The fixed account string cannot move for the first two rows.** Python reads
  them at exactly `bristlenose` (`credentials_macos.py` `ACCOUNT`; the service names beside it derive from `providers.py` `CREDENTIALS`), so the
  account-bearing methods added in `8901845f` default to it and only cloud
  sign-ins pass a derived key.
- **Derived accounts are hashed, never the raw identifier.** `kSecAttrAccount` is
  unencrypted metadata — readable in Keychain Access without unlocking the item —
  so a client's email address there is the leak this project cares about. Cloud
  mechanics (enumeration, the `unidentified` slot, the one-shot legacy migration)
  are canonical in [design-cloud-import.md](design-cloud-import.md) §7 and are
  deliberately **not** retold here.
- **The MCP bearer is the one store that is non-synchronizable by decision**
  (`MCPTokenStore.swift:157`). The reason does not generalise: that token names a server on
  *this* machine and is meaningless on another Mac. Cloud grants sync by an
  explicit 18 Aug decision; provider keys always have. Since 4 Sep 2026 there is
  a second, structural exception: every **login-keychain copy** is
  non-synchronizable by construction — the file-based keychain has no sync —
  so "synced" in the table describes the app's own copy, never the CLI's.

**`serviceNames` is an allowlist, not a naming convention.** `get` and `set` both
`guard let service = serviceNames[provider]` and bail, so an unregistered key
reads nil and writes false — **silently**. A store built on one looks entirely
correct and persists nothing; that shipped once and cost weeks of "why am I
signing in again?" (`KeychainHelper.swift`, `serviceNames`; pinned by
`CloudGrantKeychainRegistrationTests`).

**Caution when reading `hasAnyAPIKey()`:** it iterates *every* entry in that map,
so a Miro token — or a pre-migration cloud grant still at the legacy fixed key —
answers yes. It is not an API-key-only question despite the name.

Keychain fields:
- **Service:** as per the table above (what shows in Keychain Access)
- **Account:** `bristlenose` for the fixed classes; a SHA-256 hex digest for the derived ones
- **Password:** the credential itself

### 3. CLI interface

**Decision:** One provider at a time via `bristlenose configure <provider>`.

```bash
bristlenose configure claude
# Prompts for key, validates, stores in Keychain

bristlenose configure chatgpt
# Same flow

# Also: azure, gemini, miro
```

**Shipped note:** command takes **product names** (`claude`, `chatgpt`, `gemini`) in user-facing flags, not internal names (`anthropic`, `openai`, `google`). See `bristlenose/cli.py` (`configure`). Internal storage still keys on internal names, and the name `configure` prints is the stored item's, from `providers.py` `CREDENTIALS` — it printed the product-name form ("Bristlenose Claude API Key") for an item called "Bristlenose Anthropic API Key" until 4 Sep 2026.

**Not** a wizard that configures everything at once — that's rare and over-engineered.

### 4. No migration from `.env`

**Decision:** Don't offer to migrate existing `.env` keys to Keychain.

**Rationale:**
- Migration is a one-time event affecting few users (early adopters)
- Those users are technical enough to run `bristlenose configure anthropic` themselves
- Auto-migration risks confusing users ("where did my key go?")
- Simpler implementation

### 5. Credential lookup priority

> **Superseded as of 2026-08-18 — this was stated backwards, and the inversion
> is load-bearing.** Original decision preserved below the corrected box.

**Shipped behaviour (settings pipeline):** env var first, then `.env`, then Keychain. **`get_credential()` in `credentials.py` — used by the Miro route — is the other way round: store first, then env.** Two readers, opposite precedence, both shipped; a caller picks by importing one or the other, so name which you mean.

```
1. Environment variable  (pydantic-settings)
2. .env file             (pydantic-settings)
3. Keychain              (fallback for anything still unset)
```

`_populate_keys_from_keychain` fills a field only `if not settings.<field>`
(`bristlenose/config.py:702` and siblings), and `credentials_macos.py`'s own
docstring says it checks the keychain "for API keys **not already set from env
vars**".

**Why the order matters more than the preference.** The sandboxed desktop path
depends on it: the Swift host reads the Keychain and injects
`BRISTLENOSE_*_API_KEY` before spawning the sidecar, because Python cannot reach
the Keychain under App Sandbox. That injection only wins because env outranks
Keychain — under the order originally written here it would be silently ignored.

_Original decision, preserved: "Keychain first, then env var, then `.env` file.
Rationale: Keychain is the preferred storage — check it first. Env vars are
explicit overrides (useful in CI or when testing different keys). `.env` is the
fallback for users who haven't migrated." The preference is still true; the
lookup order never implemented it._

### 6. Validation before storing

**Decision:** Validate API keys with a cheap HTTP call before storing in Keychain.

**Rationale:** Easy to copy-paste a truncated key. Better to catch it immediately than have a confusing failure later during a pipeline run.

### 7. Snap confinement

**Decision:** Handle Snap later. For now, Snap users use env vars.

**Rationale:** Snap runs in a sandbox and may not have Keychain access. We'll figure out the right fallback (encrypted file in `$SNAP_USER_COMMON`?) when we get there. Don't let it block the macOS implementation.

> **Post-script (2026-04-21):** Snap shipped with env-var fallback. `bristlenose configure` detects snap context and prints an `export ANTHROPIC_API_KEY=...` message for the user to add to their shell profile. Encrypted-file approach was not needed — env vars are sufficient for snap users who are already comfortable with shell. See `docs/design-doctor-and-snap.md` (the credential paragraph) for shipped behaviour.

---

## Desktop (sandboxed) credential path

**Shipped in Track C (Apr 2026).** This is a distinct deployment from the CLI/serve-mode path above. When Bristlenose runs embedded in the macOS desktop app (sandboxed, signed, TestFlight/App Store bound), the credential flow inverts: **Swift reads Keychain via Security.framework; the sidecar never touches Keychain.** (The *CLI* on the same Mac does — it reads the login-keychain copy the app keeps of every CLI-shared key, §"One keyspace, two keychains".)

> **Beat 3 addition (2026-04-29).** A new component, `LLMValidator.swift`, reads the Keychain key inside Swift Settings to do round-trip authentication against the provider's API. It does NOT change the flow below — the env-var injection on sidecar launch is unchanged. See `design-desktop-settings.md` §"Validation flow (Beat 3)" for the validator details (verdict cache, TTL, offline survival).

> **Data-protection keychain migration (2026-06-02, commit `8b2ef51`).** The desktop store moved its *own* copy off the file-based login keychain onto the **data-protection keychain** (since 4 Sep 2026 the five CLI-shared keys keep a login-keychain copy as well — §"One keyspace, two keychains"): `kSecUseDataProtectionKeychain` on every get/set/delete, a team-scoped `keychain-access-groups` entitlement (`$(AppIdentifierPrefix)app.bristlenose`), `kSecAttrSynchronizable: true` (iCloud Keychain sync — *deliberate*: a revocable credential that also survives a damaged login keychain), `kSecAttrAccessibleAfterFirstUnlock`, and **no** biometric `SecAccessControl`. The DP keychain validates access by **Team ID, not the binary's code-directory hash** — so the host reads its own keys without a prompt across rebuilds, and the old "3× prompt cascade" (which had justified a since-removed lazy status-load) was a *legacy-keychain* artifact, not a sandbox limit (refs: Apple TN3137; steipete/CodexBar #585). Read/delete match queries on the data-protection keychain use `kSecAttrSynchronizableAny` or synced items are invisible (the login copy's queries deliberately carry neither flag — that is what routes them to the file-based keychain). Diagnose `errSecMissingEntitlement` (-34018) as an entitlement/keychain-world problem, not a damaged keychain. Canonical: `desktop/CLAUDE.md` §Key conventions + the `KeychainHelper.swift` header.

### The flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. User sets API key in SwiftUI Settings → LLM tab              │
│    → LLMSettingsView writes via KeychainHelper (Security.framework) │
│    → Keychain entry: access group scoped to app bundle ID       │
│                                                                 │
│ 2. User starts analysis                                         │
│    → ServeManager boots the sidecar subprocess                  │
│    → Before exec: overlayAPIKeys() reads the **active provider's** entry   │
│    → Injects BRISTLENOSE_<PROVIDER>_API_KEY env vars            │
│                                                                 │
│ 3. Python sidecar starts                                        │
│    → config.py reads env vars (EnvCredentialStore path)         │
│    → Never calls `security` CLI, never links Security.framework │
└─────────────────────────────────────────────────────────────────┘
```

**Anchors:**
- `desktop/Bristlenose/Bristlenose/BristlenoseShared.swift` — `overlayAPIKeys(into:)` reads the **active** provider's keychain entry and injects its env var (moved here from `ServeManager`; callers reach it via `childEnvironment`). Distinct from the Settings tab's eager all-providers status read.
- `desktop/Bristlenose/Bristlenose/KeychainHelper.swift` — Security.framework-based store (no shell-out to `security` CLI)
- `desktop/Bristlenose/Bristlenose/LLMSettingsView.swift` — SwiftUI Settings UI that calls KeychainHelper
- `desktop/Bristlenose/Bristlenose/BristlenoseShared.swift` `childEnvironment` (called from `ServeManager.start`) — subprocess boot that applies the overlay
- Commit: "inject keychain api keys as env vars" (a8dc3cb)

### Why this split

The sandboxed desktop context adds constraints that change the optimal design:

- **Sandbox entitlements.** The *host* carries the `keychain-access-groups` entitlement (load-bearing for the data-protection keychain — see the migration note above); the *sidecar* deliberately does not. Giving the Python sidecar its own keychain access would add entitlements plus a Security.framework linkage for no benefit — reading Keychain from Swift (the app's sandbox principal) and injecting credentials via process env vars keeps Python keychain-free.
- **PyInstaller bundle size.** Linking Security.framework from Python via PyObjC or similar adds weight to a bundle that's already 644 MB. The `security` CLI shell-out wouldn't work from the sandboxed Python subprocess either.
- **Separation of concerns.** The Swift side owns all OS-integration concerns (Keychain, notifications, unified logging). Python focuses on the analysis pipeline.

### Threat-model rationale

Env-var-over-keychain-access-groups has a small but non-zero residual risk: env vars are visible to anyone with the same UID via `ps -E`. The trade-off:

- An attacker with same-UID code execution on the machine can already read the **login-keychain copy** with `SecItemCopyMatching` — past macOS's ACL dialog — and the app's own data-protection copy only with the app's entitlement (an unentitled caller gets `-25300`, measured in §"One keyspace, two keychains"). Net delta from env-var exposure is small either way: same-UID code execution is not the boundary this design defends.
- The sandbox protects against *other* UIDs and untrusted cross-app actors. Both `security` CLI and Security.framework rely on the same sandbox boundary.
- Clear documentation ("same-UID threat not mitigated") is honest; hiding the env vars in Keychain access groups would be security theatre against the actual threat model.

See the comment block above `overlayAPIKeys` in `desktop/Bristlenose/Bristlenose/BristlenoseShared.swift` for the in-code rationale.

### Testability

`ServeManager` takes `any KeychainStore` as a protocol, with `InMemoryKeychain` as a test shim. Swift-side tests exercise the env-var injection path without touching the real keychain. See `desktop/Bristlenose/BristlenoseTests/` and `desktop/CLAUDE.md` §Testability refactors.

## One keyspace, two keychains

_Added 2026-09-04, from live provider testing._

**The defect.** `bristlenose configure gemini` and the app's Settings ▸ LLM
Provider both write service `Bristlenose Google Gemini API Key`, account
`bristlenose`. Keychain Access showed **two items of that name**: the app's in
**iCloud** — the data-protection keychain, `kSecAttrSynchronizable`, access
group `$(AppIdentifierPrefix)app.bristlenose` — and the CLI's in **login**. The
CLI found a stale placeholder in login while the app was Online on its own
copy; `configure` then wrote a real key to login that the app never read. Set
up in one place, invisible in the other. The requirement is the obvious one:
set up in either, and both see it.

### What was measured

Read-only probes, attributes only, no dialogs (4 Sep 2026, macOS 26.4):

| Caller | Query | Result |
|---|---|---|
| `/usr/bin/security find-generic-password` | default search list | the **login** item only. The tool has no synchronizable or data-protection flag at all (`add-generic-password -h`) |
| unentitled process — an ad-hoc `swiftc` binary, which is the CLI's situation | `SecItemCopyMatching`, legacy, no flags | the login item, **with `kSecAttrModificationDate`, without decrypting** |
| same | `kSecAttrSynchronizable: true`, legacy | `-25300` not found |
| same | `kSecUseDataProtectionKeychain` + `kSecAttrSynchronizableAny` | `-25300` not found — *allowed to ask*, cannot see the app's access group |
| same, decrypting the CLI-created login item under `SecKeychainSetUserInteractionAllowed(false)` | `kSecReturnData`, with and without `kSecUseAuthenticationUIFail` | `-25293` auth failed, **no dialog** — the process-wide toggle silences the legacy ACL prompt; the per-query key alone does not reach legacy items (SecItem.h says so in terms) |

So the tempting option — the CLI reads or writes the app's synced item — is
closed from both ends: `security` cannot address it, a Security.framework
client without the entitlement cannot see it, and PyPI/Homebrew Python carries
no signing identity that could hold one. The iCloud copy stays: it is the
18 Aug 2026 device-loss decision and nothing here reopens it.

### What was chosen

**The login keychain is the one place a sandboxed app and a shell tool can both
address, so every key the CLI reads is kept there too, and the app is the
reconciler.** `KeychainHelper.sharedWithCLI` names the five keys (exactly
`MacOSCredentialStore.SERVICE_NAMES`; `tests/test_swift_python_contract.py`
fails if the two sets drift). For those, `KeychainHelper.get/set/delete` route
through `SharedKeychainItem`, which holds two `RawKeychain`s — the
`DataProtectionKeychain` the app always had and a `LoginKeychain` addressed with
neither `kSecUseDataProtectionKeychain` nor `kSecAttrSynchronizable`, which is
what routes a query to the file-based keychains `security` searches. Cloud
sign-ins and the MCP bearer are untouched: Swift-only, synced keychain alone.

The rule, in full on `SharedKeychainItem`'s doc comment:

- **A write goes to both copies and reads both back.** `set` returns `true`
  only if the app's own copy round-tripped; a refused login copy is logged as
  the CLI's loss, not shown as a key that did not save.
- **A read compares both copies' modification dates with a ledger** (in
  UserDefaults) of what they were when they last agreed. Unchanged → read the
  app's copy, touch nothing else. The copy that moved wins: the CLI rewrote the
  login copy → adopt it into the synced one; the synced copy moved (this app,
  or another Mac via iCloud) → rewrite the login copy. Both moved, or never
  reconciled → newer wins, tie to the app's own. Only one copy exists → the
  other is made from it. Dates compare at whole seconds because login `mdat`
  carries nothing finer.
- **The login copy is replaced, never updated in place.** `SecItemUpdate` on an
  item another tool created needs that item's ACL; a delete consults none. The
  re-added item's ACL trusts the app *and* `/usr/bin/security`
  (`SecAccessCreate` + `SecTrustedApplicationCreateFromPath` — deprecated since
  10.10, still the only way to say it, and how `security add-generic-password
  -T` itself works; the deprecation is carried by a protocol witness so the
  build stays clean). Python's `set()` already deletes-then-adds, which is what
  lets it replace an app-owned login item without the app's ACL.
- **The prompt budget, and who may spend it.** The synced copy never prompts.
  Decrypting a login item another tool created raises macOS's *"Bristlenose
  wants to use your confidential information stored in … in your keychain"*
  dialog, once per such item — Always Allow (it asks for the login password)
  makes it silent. **A read is `quiet` by default and may not raise it**: every
  login-keychain call runs on one serial queue under
  `SecKeychainSetUserInteractionAllowed(false)`, a foreign item reads as
  `wouldPrompt`, the app's own copy serves, and nothing is recorded — so a spawn
  path, a launch-time model, `hasAnyAPIKey` and the **test host** never block on
  a dialog. Only Settings ▸ LLM Provider reads with `.allowed`, and that is
  where a CLI-written key is adopted. That decrypt happens only when the login
  copy has moved since the ledger last saw it, and a declined dialog is recorded
  so it is not re-asked until the copy moves again. Steady state: two attribute
  reads and one silent decrypt of the app's own copy. Why this is a rule and not
  a preference: the first run of the Swift suite against the reconciler, before
  the mode existed, read the CLI-written Gemini key at app launch, securityd
  displayed the prompt to the test host at 20:38:15, and xcodebuild reported
  *"The test runner hung before establishing connection"* six minutes later —
  the dialog was answered (Always Allow) at 22:07. In the other direction,
  whether `security -w` on an app-created item prompts is the one thing the
  probes above could not measure (it needs a team-signed writer and a dialog) —
  the ACL trust is there to prevent it; if macOS's partition list overrides it,
  the same dialog appears once in the terminal's GUI session and Always Allow
  ends it.
- **What it cannot do.** A key deleted from one keychain while the other still
  holds it comes back — absence is indistinguishable from a copy not yet made,
  and reading absence as deletion would let a locked login keychain delete a
  synced key. Delete through the app, which removes both. Over SSH with no GUI
  session, a first `security -w` on an app-created item fails instead of
  prompting; the CLI then reports no key, as it always did with a locked
  keychain.

**Python side.** `credentials_macos.py` is unchanged in mechanism — it reads
and writes the login keychain through `security`, which is now the shared
copy. `credentials.set_verified(store, key, value)` is the house read-back
helper (the Miro route's `_store_token_verified` delegates to it), and
`bristlenose configure` refuses to print *Stored in Keychain* for a key it
could not read back: exit 1, and the provider is not made current. Pinned by
`tests/test_credentials.py` (a stateful fake of `security`, so the round-trip
runs through the store's real argv without touching a developer's keychain)
and `tests/test_provider_resolution.py`.

**Swift side.** `SharedKeychainItemTests` drives the rule with two
`InMemoryRawKeychain`s that count decrypts *and dialogs* — a planted foreign
item reads `wouldPrompt` quietly and costs one `prompts` when asked — so
`quietReads_neverRaiseADialog` is the launch-safety assertion the hung runner
was missing, and `KeychainHelperTests` pins `sharedWithCLI` against the
Python-mirrored set. No test touches SecItem.

### Where each provider and credential detail lives

_Added 2026-09-04, answering "is there a single source of truth, so a change
cascades?" — the answer was no, and one copy had already drifted:
`bristlenose configure claude` printed *Stored in Keychain as "Bristlenose
Claude API Key"* for an item called "Bristlenose Anthropic API Key", since the
product-naming change._

| Detail | Source of truth | Derived from it | Hand-written mirror | What catches drift |
|---|---|---|---|---|
| Credential key (`anthropic` … `miro`), bare env var, keychain service name | `bristlenose/providers.py` **`CREDENTIALS`** | `EnvCredentialStore.ENV_VAR_MAP`, `MacOSCredentialStore.SERVICE_NAMES`, the Linux Secret Service label, the name `configure` prints | `KeychainHelper.serviceNames` and `hasAnyAPIKey`'s `nativeEnvNames` (Swift) | `tests/test_credentials.py::TestCredentialRegistry` (derivation); `tests/test_swift_python_contract.py::TestCredentialNamesContract` (the Swift strings, read from source in CI) |
| Which credentials are shared with the CLI | `CREDENTIALS`' keys | — | `KeychainHelper.sharedWithCLI` | `TestSharedKeychainContract`; `KeychainHelperTests` pins it against the Python-mirrored set |
| LLM provider display name, CLI aliases, prefixed env var, default model | `bristlenose/providers.py` **`PROVIDERS`** | `configure`'s alias map and display name; `config.py` resolution | `LLMProvider.swift` (`defaultModel`, raw values); the settings-reference tables in `frontend/src/islands/SettingsPanel.tsx` / `SettingsModal.tsx` | `TestProviderDefaultContract` (the default provider only); default models per provider are **not** pinned across the seam — a known gap |
| Pydantic env aliases (`BRISTLENOSE_X_API_KEY` / `X_API_KEY`) | `config.py` field `AliasChoices` | — | — | `TestCredentialRegistry::test_provider_env_vars_agree_with_the_credential_table` pins `PROVIDERS` ↔ `CREDENTIALS`; `config.py`'s aliases are pinned by `tests/test_credentials.py::TestUnprefixedEnvAliases` behaviourally |

**The rule this table encodes.** Change a credential's name in `CREDENTIALS`
and every Python surface follows without a second edit. Swift cannot import
Python, so its mirror is a second edit by construction — and the contract test
turns forgetting it into a red CI run rather than a user with two differently
named items. Do not add a sixth copy: a new surface that needs a credential name
reads `CREDENTIALS` (Python) or `KeychainHelper.serviceNames` (Swift), and a new
credential is a `CREDENTIALS` entry plus its Swift mirror line, nothing else.

### Verifying on a real Mac

Not automated, and not automatable without raising the dialogs above from a
harness (which the house rule on trust dialogs forbids). Expect each dialog at
most once per item; click **Always Allow**.

1. Build and launch the app. **Launch is silent** — no keychain dialog, whatever
   the CLI wrote; that is the quiet default doing its job. Open Settings ▸ LLM
   Provider: for each provider that has a CLI-written login item newer than the
   app's copy, macOS asks once — the app is adopting it. Providers then show the
   key the CLI last configured. (Gemini was already Always-Allowed for the
   Debug-signed app on 4 Sep 2026, so it may not ask at all.)
2. **App → CLI.** Save a key in the app. In a terminal:
   ```bash
   security find-generic-password -s "Bristlenose Google Gemini API Key" -w
   ```
   prints the key. If a dialog appears, it is the partition-list case above:
   Always Allow, and the next `bristlenose run` is silent.
3. **CLI → app.** `bristlenose configure gemini --key …` with a different key.
   Relaunch the app: still silent, and a run started now uses the app's *old*
   copy — by design, the spawn path may not ask. Open Settings ▸ LLM Provider:
   one dialog, the row shows the new key, and `security … -w` still prints it.
4. **Both stay agreeing.** Repeat 2 then 3; the app never shows a key the CLI
   does not, and vice versa. `bristlenose doctor` reports `(Keychain)`.

### Cleaning up a machine that already carries the split

The maintainer's Mac on 4 Sep 2026 held: an app-written iCloud item, a CLI-
written login item (`configure` deletes-then-adds by service + account, so the
stale placeholder is already gone *if* it was at account `bristlenose`), and
older login items for Anthropic (12 May), OpenAI (9 Jun) and Miro (28 Jun) that
predate or postdate the app's iCloud copies. Nothing needs deleting for the
new build to work — on first read it adopts the newer copy either way. To tidy
by hand, in **Keychain Access** (never a script — house rule):

1. Sidebar ▸ **login**. Search `Bristlenose`. Sort by Name. Two rows with the
   *same* name in login means the placeholder survived under a different
   account string: open each (double-click ▸ Attributes), keep the one whose
   **Account** is `bristlenose` and whose **Modified** is the `configure` run,
   delete the other.
2. Sidebar ▸ **iCloud**. The app's items live here. Leave them: the app
   reconciles. If you would rather start from the CLI's copy, deleting the
   iCloud item makes the app adopt the login one on next launch (one dialog).
3. Confirm from the terminal without decrypting anything:
   ```bash
   security find-generic-password -s "Bristlenose Google Gemini API Key" | grep -E '^keychain|mdat'
   ```
   One login item, modified when you last ran `configure`.

## Secret-leak defences

Shipped alongside the desktop credential path in Track C (Apr 2026). Two layers, both defence-in-depth against API-key-shaped substrings leaking into sidecar stdout / unified logging.

### Layer 1: Runtime log redactor (Swift side)

Every line of sidecar stdout passes through a regex-based redactor before forwarding to unified logging. Recognises the shape of known provider API keys and replaces with `<REDACTED>`.

- Anchors: `desktop/Bristlenose/Bristlenose/BristlenoseShared.swift` (`keyRedactionRegex` + `redactKeys`) (redactor implementation), `desktop/Bristlenose/BristlenoseTests/HandleLineRedactorTests.swift` (tests)
- Commits: "runtime log redactor for api key shapes" (8a41f60), "tests for env injection, redactor" (5dc971f)

Why runtime and not just source-time? Python logging is out of our control — third-party libraries, error messages, subprocess output. A runtime filter catches leaks the source-time gate can't.

### Layer 2: Source-time CI grep gate (Swift side)

`desktop/scripts/check-logging-hygiene.sh` — CI gate that greps Swift source for `print`/`os_log`/`Logger` calls that interpolate secret-shaped values. Fails the build if a developer writes `os_log("key: \(apiKey)")` or similar.

- Anchor: `desktop/scripts/check-logging-hygiene.sh`
- Commit: "CI grep gate for Swift logging hygiene" (c17954d)

Why both layers? Source-time catches the easy mistake before it ships. Runtime catches the hard case (library output, error messages, future code paths) where source inspection can't reach.

### What's not covered

- **Python-side logging.** The Python operational log (`.bristlenose/bristlenose.log`) is governed by `design-logging.md`'s PII policy. Not redacted at runtime — assumption is that Python-side code already avoids logging keys.
- **Shell process inspection (`ps -E`).** Same-UID attackers can read env vars. See §"Threat-model rationale" above.

---

> **Historical:** the sections below (Module Structure through Implementation Order) describe the pre-ship plan. §Edge Cases inside that range was live design reasoning rather than plan, and carries its own dated post-scripts where it has been overtaken. The approach shipped with expansion (5 providers instead of 2, Swift-side store for desktop context) but the Python-side structure is substantively as planned. Inlined source is the plan-version; see `bristlenose/credentials.py`, `credentials_macos.py`, `credentials_linux.py` for current.

---

## Module Structure

```
bristlenose/
├── credentials.py           # CredentialStore protocol + get_store()
├── credentials_macos.py     # MacOSCredentialStore (security CLI)
└── credentials_linux.py     # LinuxCredentialStore (secret-tool) + EnvFallback
```

### `credentials.py` — Protocol and factory

```python
"""Credential storage abstraction."""

from __future__ import annotations

import os
import sys
from abc import ABC, abstractmethod


class CredentialStore(ABC):
    """Abstract base for credential storage backends."""

    @abstractmethod
    def get(self, key: str) -> str | None:
        """Retrieve a credential. Returns None if not found."""
        ...

    @abstractmethod
    def set(self, key: str, value: str) -> None:
        """Store a credential."""
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove a credential. No-op if not found."""
        ...

    def exists(self, key: str) -> bool:
        """Check if a credential exists."""
        return self.get(key) is not None


class EnvCredentialStore(CredentialStore):
    """Fallback that reads from environment variables only."""

    ENV_VAR_MAP = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
    }

    def get(self, key: str) -> str | None:
        env_var = self.ENV_VAR_MAP.get(key)
        if not env_var:
            return None
        # Check both BRISTLENOSE_ prefixed and bare
        return os.environ.get(f"BRISTLENOSE_{env_var}") or os.environ.get(env_var) or None

    def set(self, key: str, value: str) -> None:
        # Can't persist to env — this is read-only
        raise NotImplementedError("Cannot store credentials in environment. Use Keychain or .env file.")

    def delete(self, key: str) -> None:
        raise NotImplementedError("Cannot delete credentials from environment.")


def get_credential_store() -> CredentialStore:
    """Get the appropriate credential store for this platform."""
    if sys.platform == "darwin":
        from bristlenose.credentials_macos import MacOSCredentialStore
        return MacOSCredentialStore()
    elif sys.platform.startswith("linux"):
        from bristlenose.credentials_linux import get_linux_store
        return get_linux_store()
    else:
        # Windows, etc. — env-only for now
        return EnvCredentialStore()
```

### `credentials_macos.py` — macOS Keychain via `security` CLI

```python
"""macOS Keychain integration using the security CLI."""

from __future__ import annotations

import subprocess

from bristlenose.credentials import CredentialStore


class MacOSCredentialStore(CredentialStore):
    """Store credentials in macOS Keychain using the security CLI."""

    ACCOUNT = "bristlenose"

    # Map internal key names to human-readable Keychain service names
    SERVICE_NAMES = {
        "anthropic": "Bristlenose Anthropic API Key",
        "openai": "Bristlenose OpenAI API Key",
    }

    def _service_name(self, key: str) -> str:
        """Get the Keychain service name for a key."""
        return self.SERVICE_NAMES.get(key, f"Bristlenose {key.title()} API Key")

    def get(self, key: str) -> str | None:
        """Retrieve a credential from Keychain."""
        try:
            result = subprocess.run(
                [
                    "security",
                    "find-generic-password",
                    "-a", self.ACCOUNT,
                    "-s", self._service_name(key),
                    "-w",  # Output password only
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            # Key not found, or Keychain locked
            return None

    def set(self, key: str, value: str) -> None:
        """Store a credential in Keychain."""
        service = self._service_name(key)

        # Delete existing entry first (security add-generic-password fails if exists)
        # Using -U (update) flag instead would be cleaner but requires the old password
        subprocess.run(
            [
                "security",
                "delete-generic-password",
                "-a", self.ACCOUNT,
                "-s", service,
            ],
            capture_output=True,  # Suppress output
            check=False,  # Ignore "not found" errors
        )

        # Add new entry
        subprocess.run(
            [
                "security",
                "add-generic-password",
                "-a", self.ACCOUNT,
                "-s", service,
                "-w", value,
                "-U",  # Update if exists (belt and suspenders)
            ],
            check=True,
        )

    def delete(self, key: str) -> None:
        """Remove a credential from Keychain."""
        subprocess.run(
            [
                "security",
                "delete-generic-password",
                "-a", self.ACCOUNT,
                "-s", self._service_name(key),
            ],
            capture_output=True,
            check=False,  # Ignore "not found" errors
        )
```

### `credentials_linux.py` — Linux Secret Service via `secret-tool`

```python
"""Linux credential storage using Secret Service (GNOME Keyring / KDE Wallet)."""

from __future__ import annotations

import shutil
import subprocess

from bristlenose.credentials import CredentialStore, EnvCredentialStore


class LinuxCredentialStore(CredentialStore):
    """Store credentials using secret-tool (libsecret)."""

    def get(self, key: str) -> str | None:
        """Retrieve a credential from Secret Service."""
        try:
            result = subprocess.run(
                [
                    "secret-tool",
                    "lookup",
                    "application", "bristlenose",
                    "key", key,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip() or None
        except subprocess.CalledProcessError:
            return None

    def set(self, key: str, value: str) -> None:
        """Store a credential in Secret Service."""
        subprocess.run(
            [
                "secret-tool",
                "store",
                "--label", f"Bristlenose {key.title()} API Key",
                "application", "bristlenose",
                "key", key,
            ],
            input=value,
            text=True,
            check=True,
        )

    def delete(self, key: str) -> None:
        """Remove a credential from Secret Service."""
        subprocess.run(
            [
                "secret-tool",
                "clear",
                "application", "bristlenose",
                "key", key,
            ],
            check=False,
        )


def get_linux_store() -> CredentialStore:
    """Get the appropriate Linux credential store."""
    # Check if secret-tool is available
    if shutil.which("secret-tool"):
        # Check if Secret Service is running (D-Bus query)
        try:
            subprocess.run(
                ["secret-tool", "lookup", "application", "bristlenose-test"],
                capture_output=True,
                timeout=2,
            )
            return LinuxCredentialStore()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    # Fall back to environment variables
    return EnvCredentialStore()
```

---

## CLI Commands

### `bristlenose configure <provider>`

Interactive command to set up a provider's API key.

```
$ bristlenose configure anthropic

Enter your Claude API key: ········
Validating...
✓ API key is valid
✓ Stored in Keychain as "Bristlenose Anthropic API Key"

You can now run: bristlenose run ./interviews
```

If validation fails:

```
$ bristlenose configure anthropic

Enter your Claude API key: ········
Validating...
✗ Invalid API key — check you copied the full key

Enter your Claude API key:
```

If Keychain is unavailable (Linux without Secret Service):

```
$ bristlenose configure anthropic

Enter your Claude API key: ········
Validating...
✓ API key is valid

No system keychain available.
Add this to your .env file or shell profile:

  export ANTHROPIC_API_KEY=sk-ant-...

(The key is not stored anywhere — you'll need to save it yourself)
```

### Implementation

```python
# In cli.py

@app.command()
def configure(
    provider: Annotated[
        str,
        typer.Argument(help="Provider to configure: anthropic, openai"),
    ],
) -> None:
    """Set up API credentials for an LLM provider."""
    from bristlenose.credentials import get_credential_store
    from bristlenose.doctor import validate_api_key  # Reuse existing validation

    provider = provider.lower()
    if provider not in ("anthropic", "openai"):
        console.print(f"[red]Unknown provider: {provider}[/red]")
        console.print("Available: anthropic, openai")
        raise typer.Exit(1)

    # Prompt for key (masked input)
    display_name = "Claude" if provider == "anthropic" else "ChatGPT"
    key = typer.prompt(f"Enter your {display_name} API key", hide_input=True)

    if not key.strip():
        console.print("[red]No key entered[/red]")
        raise typer.Exit(1)

    # Validate
    console.print("Validating...", end=" ")
    is_valid, error = validate_api_key(provider, key.strip())

    if is_valid is False:
        console.print(f"[red]✗ {error}[/red]")
        raise typer.Exit(1)
    elif is_valid is None:
        console.print(f"[yellow]! Could not validate: {error}[/yellow]")
        console.print("Storing anyway...")
    else:
        console.print("[green]✓ API key is valid[/green]")

    # Store
    store = get_credential_store()
    try:
        store.set(provider, key.strip())
        service_name = f"Bristlenose {display_name} API Key"
        console.print(f'[green]✓ Stored in Keychain as "{service_name}"[/green]')
    except NotImplementedError:
        # EnvCredentialStore — can't persist
        console.print()
        console.print("[yellow]No system keychain available.[/yellow]")
        console.print("Add this to your .env file or shell profile:")
        console.print()
        env_var = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
        console.print(f"  export {env_var}={key.strip()}")
        console.print()
        console.print("[dim](The key is not stored anywhere — you'll need to save it yourself)[/dim]")

    console.print()
    console.print("You can now run: [bold]bristlenose run ./interviews[/bold]")
```

> _4 Sep 2026:_ the `service_name = f"Bristlenose {display_name} API Key"` line in that plan is the origin of a bug that shipped — the real item is named from `credential_service_name(canonical)` (`providers.py` `CREDENTIALS`), and `configure` printed the display-name form ("Bristlenose Claude API Key" for "Bristlenose Anthropic API Key") until that day. The sample output above the plan had it right.

---

## Integration Points

### 1. Config loading (`config.py`)

Update `load_settings()` to check Keychain before env vars:

```python
def _resolve_api_key(provider: str, env_value: str) -> str:
    """Get API key from Keychain, env var, or .env file."""
    from bristlenose.credentials import get_credential_store

    # 1. Keychain
    store = get_credential_store()
    key = store.get(provider)
    if key:
        return key

    # 2. Env var / .env (already loaded into env_value by pydantic-settings)
    return env_value
```

### 2. Doctor command

Update the API key check to show source:

```
  API key        ok   Claude (Keychain)
  API key        ok   ChatGPT (env var)
```

Or with suggestion to upgrade:

```
  API key        !!   Claude (.env file — consider using Keychain)
                      Run: bristlenose configure anthropic
```

### 3. First-run prompt (existing Ollama flow)

When prompting for Claude/ChatGPT, direct users to `bristlenose configure`:

```
  [2] Claude API (best quality, ~$1.50/study)
      Run: bristlenose configure anthropic
```

---

## Testing

### Unit tests (`tests/test_credentials.py`)

```python
"""Tests for credential storage."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from bristlenose.credentials import EnvCredentialStore


class TestEnvCredentialStore:
    def test_get_with_prefix(self, monkeypatch):
        monkeypatch.setenv("BRISTLENOSE_ANTHROPIC_API_KEY", "test-key")
        store = EnvCredentialStore()
        assert store.get("anthropic") == "test-key"

    def test_get_without_prefix(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        store = EnvCredentialStore()
        assert store.get("anthropic") == "test-key"

    def test_get_prefers_prefix(self, monkeypatch):
        monkeypatch.setenv("BRISTLENOSE_ANTHROPIC_API_KEY", "prefixed")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "bare")
        store = EnvCredentialStore()
        assert store.get("anthropic") == "prefixed"

    def test_get_missing(self):
        store = EnvCredentialStore()
        assert store.get("anthropic") is None

    def test_set_raises(self):
        store = EnvCredentialStore()
        with pytest.raises(NotImplementedError):
            store.set("anthropic", "key")


class TestMacOSCredentialStore:
    @pytest.fixture
    def store(self):
        from bristlenose.credentials_macos import MacOSCredentialStore
        return MacOSCredentialStore()

    def test_get_calls_security(self, store):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="test-key\n", returncode=0)
            result = store.get("anthropic")

            assert result == "test-key"
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == "security"
            assert "find-generic-password" in args
            assert "Bristlenose Anthropic API Key" in args

    def test_get_not_found(self, store):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(44, "security")
            result = store.get("anthropic")
            assert result is None

    def test_set_deletes_then_adds(self, store):
        with patch("subprocess.run") as mock_run:
            store.set("anthropic", "new-key")

            assert mock_run.call_count == 2
            # First call: delete
            assert "delete-generic-password" in mock_run.call_args_list[0][0][0]
            # Second call: add
            add_args = mock_run.call_args_list[1][0][0]
            assert "add-generic-password" in add_args
            assert "new-key" in add_args
```

### Integration test (macOS only, skipped in CI)

```python
@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
class TestMacOSKeychainIntegration:
    """Real Keychain tests — run manually, not in CI."""

    def test_roundtrip(self):
        from bristlenose.credentials_macos import MacOSCredentialStore
        store = MacOSCredentialStore()
        test_key = "test-integration-key-12345"

        try:
            store.set("test-provider", test_key)
            assert store.get("test-provider") == test_key
        finally:
            store.delete("test-provider")
            assert store.get("test-provider") is None
```

---

## Edge Cases

### 1. Keychain locked

On macOS, if the Keychain is locked, `security find-generic-password` prompts for the user's password via a GUI dialog. This is fine — it's the expected macOS behaviour.

If running headless (SSH session without GUI), the command fails and we fall back to env vars.

### 2. Multiple keychains

macOS users may have multiple keychains. `security` uses the default keychain by default, which is correct for our use case.

> **Superseded 4 Sep 2026.** Correct for the *CLI's* copy only. The Mac app's own copy lives in the data-protection keychain, which `security` cannot address at all — the split this assumption hid, and what the app does about it, is §"One keyspace, two keychains".

### 3. Key rotation

Users can run `bristlenose configure anthropic` again to replace an existing key. The implementation deletes-then-adds, so this works.

### 4. Keychain sync (iCloud)

If the user's default keychain syncs via iCloud, the API key will sync across their Macs. This is probably fine — same user, same credentials. Document it as a "feature" (use across all your Macs).

> **Superseded 4 Sep 2026.** The login copy `security` writes never syncs — the file-based keychain has no sync. "Same key on all your Macs" is delivered by the *app's* data-protection copy (2 Jun / 18 Aug decisions), which the app re-materialises into each Mac's login keychain on first read.

---

## Not Doing

1. **`keyring` library** — adds a dependency, provides lowest-common-denominator UX
2. **Migration from `.env`** — rare, users can do it manually
3. **Windows Credential Manager** — out of scope for now (Windows isn't a target platform)
4. **Snap Keychain access** — handle later when we understand the sandbox constraints
5. **`bristlenose configure --list`** — not needed yet, `doctor` shows this info

---

## Files to Create/Modify

```
bristlenose/
├── credentials.py           # NEW: CredentialStore protocol, EnvCredentialStore, get_store()
├── credentials_macos.py     # NEW: MacOSCredentialStore
├── credentials_linux.py     # NEW: LinuxCredentialStore, get_linux_store()
├── config.py                # MODIFY: use credentials module in load_settings()
├── cli.py                   # MODIFY: add `configure` command
└── doctor.py                # MODIFY: show credential source in API key check

tests/
├── test_credentials.py      # NEW: unit tests for all stores
└── test_cli.py              # MODIFY: test `configure` command
```

---

## Implementation Order

1. **`credentials.py`** — protocol and env fallback
2. **`credentials_macos.py`** — macOS implementation
3. **`credentials_linux.py`** — Linux implementation with fallback detection
4. **`cli.py`** — add `configure` command
5. **`config.py`** — integrate with settings loading
6. **`doctor.py`** — show credential source
7. **Tests**

Estimated effort: ~4 hours
