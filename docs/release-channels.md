---
status: current
last-trued: 2026-08-14
trued-against: the §1+§3.5 release-ordering change — pypi environment hold live, publish lands at approval, bump-version no longer tags
---

# Release channels — the one-page map

> **Superseded 23 Aug 2026 — the `pypi` required-reviewer hold was REMOVED.**
> A tag push now publishes. Everything below that describes the publish job
> waiting for an approval is history, kept because the reasoning for the
> ordering still holds; only the act that lands the release moved from the
> approval to the tag. The replacement gate is the job graph:
> `publish → build → ci(strict-macos: true)`, asserted by
> `check-release-ready.sh`'s `publish gate` row. See `CLAUDE.md` § Release
> timing and `scripts/release.sh`.


Five channels. **Nothing takes a `--destination` flag.** You choose a channel by
choosing a *script* or a *trigger*, and the two Mac channels share almost nothing
but the sidecar.

| Channel | You do | Trigger | Artefact | Lifespan |
|---|---|---|---|---|
| **PyPI** | **push the tag** | tag `v*` | sdist + wheel | permanent |
| **GitHub Release** | *(nothing)* | same tag push | auto notes + assets | permanent |
| **Homebrew** | *(nothing)* | same tag push, after PyPI | tap formula bump | permanent |
| **Snap** | run the workflow by hand | `workflow_dispatch` | `.snap` → edge | permanent |
| **TestFlight** | `build-all.sh` → `upload-testflight.sh` | you, locally | `.pkg` → ASC | **90 days** |
| **Developer-ID `.dmg`** | `build-dmg.sh` → `upload-dmg.sh` | you, locally | `.dmg` → bristlenose.app | **30 days from the *build*** |

---

## One tag push does six things

Pushing tag `v*` fires `release.yml`, which runs six jobs — `ci → build →
publish`, then `github-release`, `verify-pypi` and `notify-homebrew` as
**parallel siblings** off `publish`, none gating another — and
runs to completion: CI with strict macOS, then publish. The required-reviewer
hold that used to park it was removed 23 Aug 2026 — `check-release-ready.sh`'s
`publish gate` row now asserts the `publish → build → ci(strict)` chain instead,
and fails if it breaks. There is no separate "make a GitHub release" step — it's job four.

```
ci → build (sdist, wheel, SBOMs, attestation) → publish (PyPI)
   → github-release (gh release create --generate-notes)
   → verify-pypi
   → notify-homebrew (repository_dispatch → cassiocassio/homebrew-bristlenose)
```

So **PyPI, the GitHub Release, and Homebrew are one action, not three.** Homebrew
is downstream of PyPI: the tap workflow polls `pypi.org` for the new version
before bumping the formula, so it can only succeed once PyPI has actually
accepted the upload.

**Snap is the exception — it never fires automatically.** Its `push`/`pull_request`
triggers are deliberately parked; publishing to edge is a manual
`workflow_dispatch` run.

---

## The two Mac channels do not mix

This is the easiest mistake in the repo. They are separate scripts, separate
certs, separate export plists, and **neither takes a flag**.

| | **TestFlight** | **`.dmg`** |
|---|---|---|
| Build | `desktop/scripts/build-all.sh` | `desktop/scripts/build-dmg.sh` |
| Send | `desktop/scripts/upload-testflight.sh` | `desktop/scripts/upload-dmg.sh` |
| Export plist | `ExportOptions.plist` | `ExportOptions-DeveloperID.plist` |
| Signed with | Apple Distribution | Developer ID Application |
| Checked by | App Store Connect, server-side | Apple's notary, then Gatekeeper |
| Notarised | **no** — notarytool rejects Apple Distribution | yes, twice (app + dmg) |

`build-all.sh` produces nothing bristlenose.app can serve. `build-dmg.sh`
produces nothing App Store Connect will accept.

**Why two commands per channel, not one.** Building and sending are separate
acts with different credentials, and only one is irreversible. A `--upload` flag
would be off in every run — configuration for the configurable.

---

## The commands

**CLI (PyPI + GitHub Release + Homebrew), after 9pm on working days:**

```bash
./scripts/bump-version.py minor    # or patch — minor = feature, patch = fix
# ... write CHANGELOG.md + README.md, stage, commit ...
git push origin main               # publishes nothing; buys CI signal
gh workflow run ci.yml --ref main -f strict-macos=true   # the strict verdict,
                                   # obtainable WITHOUT a tag
# ... strict CI green, Mac artefacts built + uploaded ...
git tag v<X.Y.Z>                   # after the commit — it must point at it
git push origin v<X.Y.Z>           # ← the release lands HERE. release.yml runs
                                   #   CI (strict macOS) then publishes. No
                                   #   approval step since 23 Aug 2026.
```

Then **verify PyPI actually accepted it** — a tag reaching GitHub is not a
release. Five versions silently failed to publish this way.

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://pypi.org/pypi/bristlenose/<X.Y.Z>/json
```

`200` = published. Budget 25–30 minutes; some releases have taken two hours.

**TestFlight:**

```bash
./desktop/scripts/build-all.sh
./desktop/scripts/upload-testflight.sh
```

**`.dmg`:**

```bash
./desktop/scripts/build-dmg.sh
./desktop/scripts/upload-dmg.sh --dry-run
./desktop/scripts/upload-dmg.sh
```

**Snap:** run *Snap Build & Publish* from the Actions tab.

---

## What bites

**Every TestFlight upload spends its build number forever.** ASC keys on
`(marketing version, build number)`; re-uploading the same pair is refused with a
409. A replacement needs a higher build:

```bash
./scripts/bump-version.py --build-only
```

**The `.dmg`'s 30-day clock starts at the *build*, not the upload** — sitting on
a cut costs its shelf life. TestFlight's 90 days start at upload.

**A tag push that reaches GitHub is not a release.** Always verify PyPI. If the
workflow never fired (GitHub debounces tag pushes bundled with branch pushes),
re-deliver the same SHA:

```bash
git push --delete origin v<X.Y.Z> && git push origin v<X.Y.Z>
```

But if the workflow *fired and a job failed*, that's a different fix — `gh run
rerun --failed` replays the **tagged commit**, not `main`, so a later fix on
`main` won't be picked up. Move the tag to the fixed commit instead.

**Test-only fixes reuse the tag, they don't bump it.** If a change touches only
`tests/`, `e2e/`, `docs/`, `.github/` or `.claude/`, the shipped wheel is
byte-identical — force-move the existing tag rather than forking the version line.
Counter-rule: if the version ever *published*, PyPI immutability means you must
bump.

**Releases land after 9pm London on working days — and the landing act is the
tag push.** Weekends and UK bank holidays are outside the window entirely: the
rule protects client working hours, so it has nothing to protect on a day when
clients are not working. Pushing `main` publishes nothing and can happen any time; it buys CI
signal. The **tag** is what waits for the window, because since 23 Aug 2026 it
publishes directly — there is no approval left to wait on. Weekends are
unrestricted. (The old `main:wip` preview workaround is retired — main can
simply be pushed, and wip never triggered CI anyway.)

---

## See also

- [release.md](release.md) — the CLI release process in full (version bumping, CHANGELOG conventions, the verification loop)
- [design-dmg-build.md](design-dmg-build.md) — the `.dmg` channel end to end
- [design-testflight-upload.md](design-testflight-upload.md) — the TestFlight uploader's design and the measured altool contract
- [design-homebrew-packaging.md](design-homebrew-packaging.md) — tap mechanics, and the 6.0 tap-trust trap
- `desktop/scripts/README.md` — per-script reference for both Mac channels
