---
status: current
last-trued: 2026-07-16
trued-against: HEAD@main on 2026-07-16 (first successful cut: Bristlenose-0.21.0.dmg, notarised + stapled)
---

# Building the Developer-ID `.dmg`

How we cut the notarised, stapled, **Developer-ID-signed** `.dmg` served for
direct download from bristlenose.app. This is a distinct channel from the App
Store `.pkg` path (`build-all.sh`, Apple-Distribution-signed, validated
server-side): the `.dmg` is a deliberately-disposable, build-date-**expiring**
alpha sampler (no Sparkle, no auto-update — auto-update was explicitly dropped).
Strategy (who it's for, why it expires) is out of scope here; this doc is the
*mechanics*.

**One command:** `desktop/scripts/build-dmg.sh` → `desktop/build/Bristlenose-<version>.dmg`.

## Prerequisites (one-time)

- **Developer ID Application cert** in the login keychain. Mint via **Xcode ▸
  Settings ▸ Accounts ▸ (your team) ▸ Manage Certificates… ▸ + ▸ Developer ID
  Application** — Xcode does the CSR + download + keychain install in one step,
  no portal trip. Confirm: `security find-identity -v -p codesigning | grep
  "Developer ID Application"` returns one.
  - **Back it up** as a password-protected `.p12` (Keychain Access ▸ export). The
    private key exists only on this machine — Apple keeps the public cert but
    *cannot* recover the key. Lose it → revoke + re-issue (5-cert cap; revoking
    doesn't break already-notarised software, which Gatekeeper trusts via the
    stapled ticket, not live cert validity).
  - The cert's private key lives in the **login keychain**. The first `codesign`
    use prompts *"codesign wants to access key…"*; click **Always Allow** (with
    the login-keychain password) so the ~220 inner sidecar Mach-Os and all future
    builds sign **silently**. Plain "Allow" re-prompts per binary.
- **`create-dmg`** — `brew install create-dmg`.
- **notarytool keychain profile** `bristlenose-notary` — `xcrun notarytool
  store-credentials bristlenose-notary --key <AuthKey.p8> --key-id <id> --issuer <issuer>`.

## The build chain

`build-dmg.sh` bails on any non-zero exit. Stages:

1. **Preflight** — cert present, `create-dmg`, notary profile.
2. **Sidecar** — `ensure-sidecar.sh --force`: rebuild the PyInstaller bundle and
   Developer-ID-sign every inner `.dylib`/`.so`/framework (Apple Distribution
   won't notarise; the whole tree must be Developer-ID-signed).
3. **Archive** — *development* signing (see next section).
4. **Export** — re-sign as **Developer ID** → standalone `.app`.
5. **Verify** — `codesign --verify --deep --strict` (the sandbox + Developer-ID +
   keychain-group gate) + `check-release-binary.sh` (no dev/debug literals, no
   `get-task-allow`) **before** spending notary time.
6. **Notarise + staple** the `.app` (staple so a user who drags the app out and
   discards the `.dmg` still gets a clean, offline Gatekeeper check).
7. **create-dmg** — branded window, drag-to-Applications layout.
8. **Sign + notarise + staple** the `.dmg`.
9. **Manifest** — sha256s + commit SHA.
10. **Final gates** — `spctl` accept + `stapler validate` on both `.app` and `.dmg`.

Wall-clock ~35–45 min; the two ~15-min notary round-trips dominate. `--force`
recreates the sidecar venv (clean dep closure + typeguard/`pyz+py` audit) — that
~10–15 min is deliberate for a release cut.

## The signing flow — the non-obvious bit

The app is **sandboxed** *and* carries the **Keychain Sharing**
(`keychain-access-groups`) entitlement — required so `KeychainHelper`'s
data-protection keychain can store provider API keys. **Xcode treats that
entitlement as provisioning-profile-gated, even for Developer ID.** So you
cannot force Developer-ID signing at *archive* time with an empty profile — it
dies `"…requires a provisioning profile."`

**Verified dead ends (16 Jul 2026 — don't re-try these):**

| Attempt | Result |
|---|---|
| Force `CODE_SIGN_IDENTITY="Developer ID Application"` + empty `PROVISIONING_PROFILE_SPECIFIER` at archive | ❌ "requires a provisioning profile" |
| Hardcode the Team-ID prefix in the entitlement (`Z56GZVA2QB.app.bristlenose` vs `$(AppIdentifierPrefix)…`) | ❌ still fails — it's the *capability* Xcode gates on, not the variable |
| `CODE_SIGN_STYLE=Automatic` with a Developer ID identity | ❌ automatic signing only does *development*; refuses the Developer-ID identity |
| Drop `keychain-access-groups` for the `.dmg` build | ❌ breaks the data-protection keychain (`-34018 errSecMissingEntitlement`); API-key storage fails, so the user can't configure a provider |

**The working path is Apple's standard archive→export split:**

1. **Archive with automatic *development* signing** (`CODE_SIGN_STYLE=Automatic`,
   `CODE_SIGN_IDENTITY="Apple Development"`, `-allowProvisioningUpdates`) — this
   succeeds because it uses the auto-managed **"Mac Team Provisioning Profile,"**
   which *does* carry the keychain entitlement. The `DEVELOPER_ID_BETA`
   compilation flag is baked here.
2. **Export as Developer ID** — `ExportOptions-DeveloperID.plist` with
   `method=developer-id` + `signingStyle=automatic` (no `signingCertificate`
   key), and `xcodebuild -exportArchive -allowProvisioningUpdates`. Xcode
   **mints a Developer ID provisioning profile on the fly** (no portal trip) and
   re-signs. `DEVELOPER_ID_BETA` persists because export re-signs, doesn't
   recompile.

Wired into `build-dmg.sh` steps 3–4 and `ExportOptions-DeveloperID.plist`; the
full rationale is duplicated in those files' comments.

## Verifying the artifact

The acceptance signal that it'll open cleanly on a fresh Mac (one *"downloaded
from the Internet — Open?"* tap, **not** the "unidentified developer" wall):

```sh
# mount the .dmg, then on the app INSIDE it (what a downloader evaluates):
spctl -a -t exec -vv "/Volumes/…/Bristlenose.app"   # → accepted; source=Notarized Developer ID
stapler validate "…/Bristlenose.app"                # → "The validate action worked!" (offline ticket)
```

`source=Notarized Developer ID` is the gold standard. Expiry is
build-date-anchored (`AlphaBuild.swift`, ~30 days from `GeneratedBuildInfo.buildDate`),
so a fresh cut is good for ~30 days — re-cut to refresh the public download.

## Publishing

`scp` the `.dmg` to the server as the **stable** name `Bristlenose.dmg` (do this
**before** the site deploy, or the live CTA 404s), then deploy the website so the
"Download for Mac" button goes live. The website lives in a separate repo; its
`deploy.sh` protects the `dmg/` dir through rsync `--delete`, and the permanent
public URL is `/dmg/Bristlenose.dmg` (never versioned — re-cutting refreshes it
in place).

## See also

- `desktop/scripts/build-dmg.sh` — the script; header carries the same rationale.
- `desktop/Bristlenose/ExportOptions-DeveloperID.plist` — export config + the
  provisioning-gotcha comment.
- `docs/design-desktop-build-orchestration.md` — the App Store `build-all.sh`
  sibling path.
- `docs/design-homebrew-packaging.md` — the CLI packaging channel.
