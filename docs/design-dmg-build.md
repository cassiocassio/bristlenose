---
status: current
last-trued: 2026-08-14
trued-against: the one-round-trip notary model (app-level notarisation retired, "stop paying Apple twice"); previously 2026-08-04 against the 0.24.0 publish
---

# Building the Developer-ID `.dmg`

## Changelog

- _2026-08-14_ — trued up: app-level notarisation retired (one notary round
  trip, on the image; step 6 is now a documented absence), §Verifying rewritten
  — the inner app is deliberately ticketless so `stapler validate` on it FAILS
  by design; the gate asserts `codesign --deep --strict` instead and its inner
  `spctl` verdict resolves via **online** ticket lookup (new network
  dependency). Step 2 gains the pre-sign `doctor --self-test`. Anchors:
  `desktop/scripts/build-dmg.sh:23-26,301-322`,
  `desktop/scripts/check-dmg-shippable.sh:127-151`,
  `desktop/scripts/ensure-sidecar.sh:149-185`, commits "stop paying Apple
  twice: one notary round trip, one 675MB transfer", "run the bundle self-test
  where it can actually run".
- _2026-08-04_ — trued against the 0.24.0 cut-and-publish (notarytool
  mid-upload crash, versioned artefact + stable redirect verified live).

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
2. **Sidecar** — `ensure-sidecar.sh --force`: rebuild the PyInstaller bundle,
   run `doctor --self-test` on it **pre-sign** (the only window it can run —
   sandbox-signed it aborts standalone; writes `.selftest-stamp`), then
   Developer-ID-sign every inner `.dylib`/`.so`/framework (Apple Distribution
   won't notarise; the whole tree must be Developer-ID-signed).
3. **Archive** — *development* signing (see next section).
4. **Export** — re-sign as **Developer ID** → standalone `.app`.
5. **Verify** — `codesign --verify --deep --strict` (the sandbox + Developer-ID +
   keychain-group gate) + `check-release-binary.sh` (no dev/debug literals, no
   `get-task-allow`) **before** spending notary time.
6. *(retired 14 Aug 2026)* — app-level notarisation is deliberately absent.
   The `.dmg` submission in step 8 covers the nested app's cdhashes; what the
   separate round trip bought was offline first-launch of a dragged-out app,
   traded away for halving the lane's slowest stretch. See §Verifying below.
7. **create-dmg** — branded window, drag-to-Applications layout.
8. **Sign + notarise + staple** the `.dmg` — the ONE notary round trip.
9. **Manifest** — sha256s + commit SHA.
10. **Final gates** — delegated to `check-dmg-shippable.sh`: `spctl` accept +
    `stapler validate` on the image; `codesign --deep --strict` + `spctl` on
    the app inside it (no staple check there — see §Verifying).

Wall-clock ~25–35 min; the single ~15-min notary round-trip dominates (it was
two until 14 Aug 2026 — the lane was halved by dropping app-level notarisation,
not by Apple getting faster). `--force`
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

**The manifest records a dirty tree; it does not refuse one.** Deliberate,
decided 4 Aug 2026. The `.dmg` is the one channel with no update mechanism
behind it, so a hard gate on `git status` looks obviously right — but it would
have refused that very day's cut (`build-dmg.sh` was itself uncommitted), and a
gate that refuses routine work gets `--allow-dirty`'d by reflex within a week.
The honest `tree: dirty — N modified, M untracked` line is the real control:
split modified-from-untracked, because an always-on flag is an ignored flag and
this tree carries untracked scratch as a matter of course. If a refusal is ever
wanted, the **publish** boundary is its natural home, not the build.

## When notarisation goes wrong

Learned expensively on 4 Aug 2026 — a crash mid-upload cost about fourteen
hours, almost all of it spent waiting for something that was never going to
arrive. The script now encodes all of this; the reasoning is here so nobody
un-encodes it.

**Never submit with `--output-format plist` (or `json`).** Both buffer to
completion — notarytool's own help says "a single update will be output at the
end of the operation" — so a client crash during the upload leaves a
**zero-byte file** and the submission ID exists nowhere on the machine. Normal
format prints `id: <uuid>` *before* the upload begins, so `tee` captures it
while the transfer is still in flight. A crash then leaves something resumable
rather than a mystery. Keep the machine-readable formats for `info` and `log`,
which are short calls that complete atomically.

**A submission that dies mid-upload may not exist at Apple at all.** The 0.24.0
orphan never appeared in `notarytool history`, and by the next morning
`notarytool info` on its ID returned *"Submission does not exist or does not
belong to your team"* — Apple had purged it. So there is no "adopt the orphan"
recovery path to build. The policy is: **no captured ID → resubmit; captured ID
→ ask `notarytool info` and believe it.**

**`info` distinguishes three states, and they need different responses.** This
is the distinction that cost the fourteen hours, because a poll loop that
collapses them will wait for a corpse:

| Reading | Means | Do |
|---|---|---|
| `In Progress` | queued at Apple | wait — resubmitting just queues behind it |
| `Accepted` / `Invalid` | terminal | staple, or read `notarytool log` for the issues |
| *"Submission does not exist"* | Apple never took it, or purged it | resubmit immediately |

The third is **terminal, not pending.** Treating an empty or missing status as
"keep waiting" is a fail-open, and it is exactly what turned a two-minute
recovery into an overnight one.

**Cap the wait.** A clean resubmit of the same 644 MB came back `Accepted`
within minutes while the orphan had been "pending" for eleven hours. If a
submission dies without a verdict, retrying once with `--no-s3-acceleration`
uses Apple's documented alternate upload path.

**Retry the staple.** `stapler staple` *downloads* the ticket, and it can 404
briefly after `Accepted` while the ticket propagates (Error 65). Unretried,
that throws away a round trip you have already paid for. Assert success with
`stapler validate`, not with staple's own exit code.

## Verifying the artifact

The acceptance signal that it'll open cleanly on a fresh Mac (one *"downloaded
from the Internet — Open?"* tap, **not** the "unidentified developer" wall):

```sh
# mount the .dmg, then on the app INSIDE it (what a downloader evaluates):
spctl -a -t exec -vv "/Volumes/…/Bristlenose.app"   # → accepted; source=Notarized Developer ID
codesign --verify --deep --strict "…/Bristlenose.app"   # → signature valid, deep and strict
```

**Do NOT assert `stapler validate` on the inner app — it fails by design.**
Since 14 Aug 2026 the app inside the image carries no ticket: only the `.dmg`
is notarised and stapled, and its ticket covers the app's cdhashes. The `spctl`
verdict on the inner app therefore resolves via an **online ticket lookup** —
which is exactly what it proves (the dmg's notarisation reaches this app), and
means the acceptance check needs network. The traded-away guarantee: first
launch of a dragged-out app on a fully offline Mac needs one online check to
clear quarantine; every later launch is offline-clean. Restore path if that
ever matters (air-gapped channel): `notarize_and_staple "$APP"` before
create-dmg, and revert the gate's inner-app check to a staple assertion.

`source=Notarized Developer ID` is the gold standard. Expiry is
build-date-anchored (`AlphaBuild.swift`, ~30 days from `GeneratedBuildInfo.buildDate`),
so a fresh cut is good for ~30 days — re-cut to refresh the public download.

**This is now mechanical — `desktop/scripts/check-dmg-shippable.sh <dmg>`** runs
the above (mount, assert on the app *inside* — signature + Gatekeeper, the
latter needing network for the ticket lookup — detach) plus the filename
↔ `Info.plist` version agreement and a manifest ↔ image sha256 check. Step 10
delegates to it, and any upload path must call it as a **precondition**, not as
a step an operator can skip.

It was prescribed here and unimplemented for a long time, and the gap was not
theoretical. Until 4 Aug 2026 step 10 asserted against `$EXPORT_DIR`'s `.app` —
the export source, not the copy inside the image — and its two `stapler validate`
lines were written `stapler validate X && ok "…"`, which `set -e` exempts, so a
failure printed nothing and fell through to the success banner. The one check
that *would* have caught an unnotarised artefact was the check nobody had
written.

**Why the app inside the image is the one that matters:** `create-dmg` takes a
**copy** — any check against the export-dir original proves nothing about the
bytes a user receives. That lesson (4 Aug 2026) still governs the gate's
mount-and-interrogate design.

> **The offline-launch argument below described the OLD model and is retained
> as the record of what was traded away (14 Aug 2026).** With the inner app
> unstapled by design, the offline-drag scenario now costs one online check on
> first launch — accepted deliberately for a 30-day expiring sampler whose
> user just pulled 660 MB over the network. Original reasoning: a user who
> drags the app out, bins the `.dmg` and opens it offline gets *"Bristlenose
> can't be opened because Apple cannot check it for malicious software"*; on
> Sequoia+ right-click → Open no longer bypasses that. That failure mode is
> now reachable only with zero network on first launch.

## Publishing

**One command — `desktop/scripts/upload-dmg.sh`.** First cut published with it:
0.24.0 on 4 Aug 2026.

```sh
desktop/scripts/upload-dmg.sh --dry-run   # probes the host read-only, changes nothing
desktop/scripts/upload-dmg.sh             # publishes
```

It gates on `check-dmg-shippable.sh` as a **precondition**, stages to a
dot-prefixed name **in the target directory** (`mv` is only atomic within a
filesystem — staging elsewhere would degrade to copy+unlink and reopen the
truncated-download window), verifies the sha256 of the bytes that landed,
`chmod 644` before the rename (a new file gets a new inode at `0666 & ~umask`,
not the old mode — otherwise the download 403s), swaps, repoints the permalink,
and reaps all but the newest N. If identical bytes are already on the host under
a name it recognises, it copies server-side instead of re-sending.

Do this **before** the site deploy, or the live CTA 404s. The website lives in a
separate repo; its `deploy.sh` protects the `dmg/` dir from rsync `--delete`, so
nothing else ever cleans that directory and retention is this side's job.

Run `--dry-run` every time. It costs seconds and it checks ssh under
`BatchMode`, the target dir, remote `shasum`, and free space — the things that
otherwise fail forty minutes in, at 3am, with nobody awake.

**Two URLs, and they answer different questions. Don't collapse them.**

| URL | Means | Serves |
|---|---|---|
| `/dmg/Bristlenose.dmg` | "the current alpha" — redirects to the versioned file | The LinkedIn/Substack link, the site CTA, the docs. Never 404s, always live. |
| `/dmg/Bristlenose-0.24.0.dmg` | "this exact build" — immutable | Pinning, bug reports, "which one were you on?" |

A stable URL whose content changes is the right shape *for this channel
specifically*: builds expire after 30 days, so a three-week-old post handing
someone a build that died last Tuesday is worse than one handing them the
current cut. The stable name is a permalink to a **concept**, not to a file.

**Verified live, 4 Aug 2026** — these were assumptions until the first publish:

```
/dmg/Bristlenose.dmg         → HTTP 302 → /dmg/Bristlenose-0.24.0.dmg
/dmg/Bristlenose-0.24.0.dmg  → HTTP 200, 674773487 bytes
```

The redirect lives in `/dmg/.htaccess`, and that file is **written by
`upload-dmg.sh` on every publish** — it is not pre-existing server config, so
don't hunt for it in the website repo; the uploader owns it (and the documented
rollback is editing its `Redirect` line to point at a previous versioned file).

The redirect **takes precedence over a real file of the same name**. mod_alias
resolves the URL before the filesystem is consulted, so the pre-redirect
`Bristlenose.dmg` still sitting in that directory is unreachable — which is the
good news for the transition and the bad news for the quota. Those bytes are now
orphaned and nothing reaps them; remove the legacy file by hand once you're
satisfied the permalink behaves.

**A stapled `.dmg` is bigger than the one `create-dmg` reported.** 0.24.0:
`create-dmg` printed `674757575`, the served file is `674773487` — **+15,912
bytes of stapled ticket**. So a size assertion against the build log reads as a
mismatch on a *correctly* stapled image. Compare hashes, and compare them
against the manifest, which is written after stapling.

**Superseded 4 Aug 2026 — this doc previously said the public URL was "never
versioned — re-cutting refreshes it in place".** Two problems with that, and
they pull in opposite directions, which is why the answer is both URLs rather
than either one:

- **On disk, the downloader can't tell what they have.** A file called
  `Bristlenose.dmg` in Downloads explains nothing when it stops working six
  weeks later. That is support load you never see, from people who won't write
  in.
- **A bare versioned URL breaks every link already published.** This channel's
  whole distribution mechanism is a link in a post.

**Redirect, not a symlink.** Apache follows a symlink to read the bytes, but the
request path is still `/dmg/Bristlenose.dmg`, and the browser names the download
from the URL — so a symlink fixes the link-rot half and leaves the
what-have-I-got half exactly as broken. Browsers derive the filename from the
*final* URL after a redirect, so a redirect fixes both. (`Content-Disposition`
would also work and keeps one clean URL, but hides the version until the file is
already saved, and `curl -O` ignores the header without `-J`.)

Rollback is repointing the redirect at the previous versioned file — no
re-upload, and the reason no separate `.prev` mechanism is needed.

Two consequences worth building for: verification must assert the **effective**
URL's host and filename rather than accepting a 200, since a redirect that lands
somewhere unexpected otherwise surfaces as a baffling hash mismatch; and the
stable URL is never cached *as content*, which sidesteps the 48-hour `max-age`
on the versioned files.

## See also

- `desktop/scripts/build-dmg.sh` — the script; header carries the same rationale.
- `desktop/Bristlenose/ExportOptions-DeveloperID.plist` — export config + the
  provisioning-gotcha comment.
- `docs/design-desktop-build-orchestration.md` — the App Store `build-all.sh`
  sibling path.
- `docs/design-homebrew-packaging.md` — the CLI packaging channel.
