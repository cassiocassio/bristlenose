---
status: current — first run 8–9 Oct 2026 (0.36.0, microsoft/winget-pkgs#449372)
---

# Shipping a version to winget

The per-release procedure, as run by hand for 0.36.0, and what went wrong on the way.
The plan and its reasoning are in `docs/design-winget.md`. This page covers the
mechanics only.

winget is **not yet a release-machine channel**. `release.sh` does not run any of
this, and `release.sh verify` does not check it. Automation (`winget-releaser`, a
channel row in `scripts/project.conf`) is step 5 of the plan, after one or two
accepted versions.

## The shape

```
tag vX.Y.Z pushed
  → windows-installer.yml on the tag   (builds, smoke-tests, fills + schema-checks the manifest)
  → download that run's artefact        (the installer, the three manifest files, the log)
  → attach the installer to the GitHub Release, then check the public download's hash
  → komac submit the manifest directory → a PR on microsoft/winget-pkgs
  → bot validation (antivirus, Defender after a real install) → moderator → merge
  → `winget install --id Bristlenose.Bristlenose -e` works for everyone
```

Merging takes days for a new package. Later versions should be quicker, but that
hasn't been measured. Until the PR merges, winget still serves the previous version.

## Steps

All commands run on the Mac, from the repo root.

**1. Build on the tag.** Run this only after `vX.Y.Z` is on `origin`:

```bash
gh workflow run windows-installer.yml --ref vX.Y.Z
```

The run takes about 6.5 minutes. It builds the wheel from the tag, runs PyInstaller,
runs the nine smoke checks in `packaging/windows/smoke.ps1`, compiles the installer
with Inno Setup 7.1.0 (pinned by SHA-256), fills the manifest and checks it against the
vendored winget schemas. Read the log's last lines. "All smoke checks passed." and
"Manifest schema validation passed." must both be there.

**2. Download the artefact.** Use that run's id, from `gh run list --workflow windows-installer.yml -L 1`:

```bash
gh run download <run-id> -n bristlenose-windows-installer -D <scratch-dir>
```

The installer lands at `<scratch-dir>/build/windows/bristlenose-X.Y.Z-setup-x64.exe`,
and the manifests at `<scratch-dir>/build/windows/winget/Bristlenose.Bristlenose/X.Y.Z/`.
Compare the installer's `shasum -a 256` with the `InstallerSha256` in
`Bristlenose.Bristlenose.installer.yaml`. Then fetch every URL in the three files,
because winget's bot does and a single 404 fails the PR:

```bash
grep -hoE 'https?://[^ "]+' <manifest-dir>/*.yaml | sort -u | while read u; do echo "$(curl -sL -o /dev/null -w '%{http_code}' "$u") $u"; done
```

The installer URL will 404 until step 3 attaches it; every other URL must be 200.

**3. Attach it, then check what the public gets.**

```bash
gh release upload vX.Y.Z <scratch-dir>/build/windows/bristlenose-X.Y.Z-setup-x64.exe
```

Then `curl -sL` the public URL
(`https://github.com/cassiocassio/bristlenose/releases/download/vX.Y.Z/bristlenose-X.Y.Z-setup-x64.exe`)
and hash the download. It must match the manifest. That URL is the one the manifest
names, and winget refuses an installer whose hash differs.

**4. Dry run, then submit.** You need Komac (`HOMEBREW_NO_ASK=1 brew install komac`;
2.16 on 8 Oct 2026) and a fork of winget-pkgs under the account (see Gotchas).

```bash
GITHUB_TOKEN=$(gh auth token) komac submit --dry-run <manifest-dir>
```

```bash
GITHUB_TOKEN=$(gh auth token) komac submit --yes <manifest-dir> > komac-submit.log 2>&1
```

Read the whole log; it names the PR. Komac commits the three files to
`manifests/b/Bristlenose/Bristlenose/X.Y.Z/` on a branch of the fork and opens the PR.
One version per PR.

**5. The CLA (first PR only), signed by Martin himself.** Martin posts this comment on
the PR, as an individual with no company:

```
@microsoft-github-policy-service agree
```

Nobody else can post it on his behalf. The `Needs-CLA` label blocks validation until he
does.

**6. Watch the labels.** Use `gh pr view <n> --repo microsoft/winget-pkgs --json labels,comments`.
What comes back:

- **Validation completed / Azure-Pipeline-Passed:** waiting on a moderator. Nothing
  to do.
- **A Defender or antivirus flag:** most likely a PyInstaller false positive. Submit
  the installer at microsoft.com/wdsi/filesubmission, signed in as
  `martin@bristlenose.app` (the Microsoft identity from the Teams testing). After the
  verdict, comment `@wingetbot run`.
- **An installer-analysis failure naming Inno Setup:** see the Inno 7 gotcha below.
  Rebuild with Inno 6.7, replace the release asset, update the hash, and push to the
  same PR branch.
- **A moderator question:** answer it on the PR.

**7. After the merge.** Run `winget search Bristlenose` on any Windows machine. Then
`winget install --id Bristlenose.Bristlenose -e`, and confirm that `winget list --id`
and `winget uninstall --id` find it. Those last two can't be tested before publication
(see below). The user-facing docs that name winget go live then, from the waiting
branches, with Martin's OK.

## Gotchas

Each of these cost a cycle at least once.

**Release mechanics**

- **winget's bot fetches every URL in the manifest, and the schema check can't.**
  0.36.0's first validation failed on `ReleaseNotesUrl:
  https://bristlenose.app/changelog.html`, which was a 404. The changelog lives at
  `/docs/changelog.html`, since the website v2 cutover. The fix went onto the PR branch
  as a commit to the fork (any later push re-runs validation), and into the template.
- **Never rebuild a published version's installer.** Two builds of the same commit
  differ in hash (timestamps inside the installer), and winget pins the hash. Upload
  the artefact built on the tag. If the installer really has to change, the manifest's
  hash changes with it, in the same PR, before the merge.
- **Upload from the artefact directory, not the current directory.** A bare
  `gh release upload vX.Y.Z bristlenose-X.Y.Z-setup-x64.exe` fails with "no such file",
  because the artefact unpacks under `build/windows/`.
- **Komac's `submit` needs the fork to exist already.** Without it, the error is
  `Could not resolve to a Repository with the name 'cassiocassio/winget-pkgs'`. Create
  it with `gh repo fork microsoft/winget-pkgs --clone=false --default-branch-only`,
  then poll `gh repo view cassiocassio/winget-pkgs` until it answers. A fork takes
  seconds to appear. A failed submit creates nothing, so retrying is safe.
- **Komac's `analyze` refuses Inno Setup 7** ("newer than the maximum supported version
  6.7"). `submit` with prebuilt manifests never analyzes, so it isn't blocked. winget's
  own validation pipeline may use similar parsing. If it fails on this, the fallback is
  Inno 6.7: change `INNO_VERSION`/`INNO_SHA256` in `windows-installer.yml`, after
  checking that `bristlenose.iss` compiles under 6.x.
- **Send Komac's output to a file; don't filter it.** On the first submit attempt, a
  `grep -v` meant to strip manifest echo also hid the error, and the failure looked
  like silence.
- **Redact the token.** `GITHUB_TOKEN=$(gh auth token)` puts a `gho_…` value in the
  environment. Any output you keep goes through
  `sed -E 's/gh[opsu]_[A-Za-z0-9]+/[token]/g'`.
- **The identifier is `Bristlenose.Bristlenose`, and the docs always say
  `--id Bristlenose.Bristlenose -e`.** winget matches IDs case-insensitively, but `-e`
  (exact) is case-sensitive. The doubled name is the convention (`Obsidian.Obsidian`,
  `Spotify.Spotify`, `Ollama.Ollama`) and can't be renamed without a migration.
- **winget lags PyPI by the moderator queue.** Expect days for a new package. The
  version-skew question across channels is open; nothing in the public docs addresses
  it yet, by decision.

**Testing the installer before submitting**

- **GitHub's Windows runner can't install winget.** `Add-AppxPackage` fails with "does
  not have an appropriate application package for x64". CI therefore checks the
  manifest against winget's JSON schemas, vendored at
  `packaging/windows/winget/schemas/1.12.0/`, using `validate_manifest.py`. That covers
  the structure, not the download or the hash. `winget validate` and
  `winget install --manifest` need a real Windows machine (an aella box or the UTM VM).
- **`winget install` of an unsigned installer shows SmartScreen.** winget applies the
  Mark of the Web itself. A headless `winget install --manifest` over SSH therefore
  waits forever on a dialog nobody can see. Test from a desktop session (`aella rdp`),
  or start the install from a scheduled task with an Interactive principal, so the
  dialog appears where someone can click Run anyway. Signing (Certum, November 2026)
  is what removes the dialog.
- **A local-manifest install can't be listed or uninstalled by ID.** `winget list --id`
  and `winget uninstall --id` find nothing, because a local manifest isn't a source
  winget can match against. Those two checks only work after publication.
- **A bare `winget install FFmpeg` can fail outright.** It also queries the msstore
  source, and on Windows Server 2025 that failed with `0x8a15005e` instead of falling
  back. Name the package: `winget install --id Gyan.FFmpeg -e --source winget`.
  (Advice only; the installer bundles its own FFmpeg.)
- **Tear the aella box down as soon as the test ends** (`aella down -y`). An idle box
  costs money and finds nothing.

**The build and the installer** (fixed; the tests in
`tests/test_windows_packaging.py` pin each one)

- **The build packaged the checkout instead of the wheel** when run from the repo root.
  PyInstaller's `pathex` and the current directory on `sys.path` won over the installed
  wheel. Fixed with `pathex=[]` and `python -P`, and `build.ps1` now asserts the
  package directory is inside the build venv.
- **A non-admin upgrade over a running `serve` broke the install.** Restart Manager's
  `RmGetList` fails for a normal user, and the rollback left `bristlenose.exe` without
  `_internal`. The installer and uninstaller now refuse while the exe is locked: a
  `TFileStream` write-open probe, with exit 7 on install, which the manifest maps to
  `packageInUse`. A WMI process query was the first attempt; WMI denied it to the
  non-admin user, and it failed open.
- **PowerShell 5.1 under `$ErrorActionPreference = 'Stop'`** (GitHub's default) turns
  any stderr line from a native tool into a terminating error. One example is uv's
  "Using CPython …". A pipeline also leaves `$LASTEXITCODE` unreliable. CI runs
  `build.ps1` through `cmd /c "… > build-windows.log 2>&1"` and reads the exit code
  after.
- **ISCC reported its version as 0.0.0.0.** `build.ps1` reads it from the Inno Setup
  Uninstall registry entry instead.
- **PyYAML parses `ReleaseDate: 2026-10-08` as a date**, which the schema's
  `"type": "string"` rejects. `validate_manifest.py` loads without the timestamp
  resolver, as winget does.
- **Template comments and unfilled placeholders.** `build.ps1` strips the
  `# Template:` lines and refuses a manifest still holding a placeholder. The check
  uses `-cmatch` (case-sensitive), because PowerShell's `-match` ignores case.
- **The frozen build must use its own FFmpeg or nothing.** `bundled_binary_path` returns
  `tools\ffmpeg.exe` or `None` in a frozen Windows build and never falls back to PATH.
  On Windows, `which()` searches the current directory first.
