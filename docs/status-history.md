# Status history — the paragraphs `CLAUDE.md` carried, by release

Moved verbatim from the root `CLAUDE.md`'s **Current status** section on 16 Oct 2026, to cut what
every session loads on every turn. Each release's own account is in [`release-log.md`](release-log.md)
(complete from 0.30.0; 0.29.x lives only here) and its user-facing notes in `CHANGELOG.md`.
Not updated any more: a release writes its account in the release log.

---

**Internal TestFlight since 14 Jul 2026** — shipping build **0.38.0 (5002)** — first build accepted by App Store Connect: **0.20.0 (2068)**, App-Sandbox + Hardened-Runtime + arm64-only, signed Apple Distribution.

**0.38.0 shipped 16 Oct 2026, overnight and unattended — tag `v0.38.0` on `65501668`, TestFlight
build 5002, verified 9 of 9.** A minor: lenses readable during a first analysis, the Screens lens,
project identity by id and content, the scene timeline, eleven more Whisper prompt languages. Five
strict-CI rounds, all Windows or gates, none in the product's main path; one Windows test is skipped
with its open-database holder still to find (TODO.md). Full account: `docs/release-log.md` § 0.38.0.

**0.37.0 shipped 12 Oct 2026, overnight and unattended — tag `v0.37.0` on `c236d797`, TestFlight
build 4695, verified 9 of 9.** A minor: punctuated Whisper output, Word tables read, PII redaction on
Snap and Copr, and the session start time. Three stops, none in the product: four tests that read
their machine, huggingface-hub 2.x arriving through tokenizers (capped `<2`), and our own spacy-models
URL tripping the App Store string gate (now stripped in the spec). Full account: `docs/release-log.md`
§ 0.37.0.

**0.36.0 shipped 8 Oct 2026, late evening — tag `v0.36.0` on `e08a44d5`, TestFlight build
4588, verified 9 of 9.** A minor: transcript copy across paragraphs (Markdown and Word rich
text), sentence-start capitals, and the speaker-label leak past anonymisation. Three attempts,
each stopped by a test, none by the product: Windows tests reading the runner's ffmpeg after the
`safe_which` change, and a perf test on vitest's 5 s default. Full account:
`docs/release-log.md` § 0.36.0.

**0.35.0 shipped 7 Oct 2026, overnight and unattended — tag `v0.35.0` on `acc9feb8`,
TestFlight build 4528, verified 9 of 9.** A minor: the session timeline under each Sessions
row, role recodes in the person picker (now on the transcript and dashboard too), one-session
re-analyse, and split/join/move for transcript paragraphs. The run itself went clean, 65 min to
tag; the work was before it — `main` was red on four blocking checks from the day's commits,
including a Swift expression that timed out CI's type-checker. Full account:
`docs/release-log.md` § 0.35.0.

**0.34.0 shipped 5 Oct 2026, evening — tag `v0.34.0` on `4c5855b5`, TestFlight
build 4420, verified 9 of 9.** A minor: the CLI on Windows, the one-line installer
(`bristlenose.app/install.ps1`), and winget Ollama in `configure local`. Drafted as 0.33.1;
the winget feature made it a minor. Five stops, none in the product: two CI tests that read
their machine, a stranded step, one transient Swift host exit, and a `.dmg` upload whose
resume had never worked (`62a8c7dc`). Full account: `docs/release-log.md` § 0.34.0.

**0.33.0 shipped 4 Oct 2026, evening — tag `v0.33.0` on `f1d396ff`, TestFlight
build 4372, verified 9 of 9.** A minor: the Discussion lens, a voice
pass in speaker identification (onnxruntime, every channel, no espeak-ng), the person picker,
search with person and tag tokens, and Undo. Ten sessions coordinated from one; two stops,
neither in the product — a lapsed Apple agreement (notary 403) and the `.dmg`'s Swift suite
failing on a locked screen, now prevented by `caffeinate -d`. Full account:
`docs/release-log.md` § 0.33.0.

**0.32.0 shipped 30 Sep 2026, overnight — tag `v0.32.0` on `d49df5d4` at
01:31 BST, TestFlight build 4035, verified 9 of 9.** A minor: clip subtitles (a `.vtt` and a
language-tagged track per clip, an optional burned-in copy, CJK line breaking),
subtitles and keyboard controls in the video player, and agent access through a
native sandboxed helper — **Install Plugin…** for ChatGPT, and a Claude extension
that needs no Files & Folders step on macOS 27. Six attempts, none for a product
defect: PyAV 19 shipped that evening and broke faster-whisper's decoder (pinned
`av<19`, and 0.31.5 fresh installs off the Apple-Silicon Mac app were broken
until the tag); two ratchets the helper's own tests pushed over; the `.dmg` gate
still refusing *any* app group, written before the helper made the team group
part of the Developer-ID contract; two dependency publishes mid-run; and two
tests green here and red on every CI cell. Full account: `docs/release-log.md`
§ 0.32.0.

**0.31.5 shipped 29 Sep 2026, overnight and unattended — tag `v0.31.5` on
`e173aaa1`, TestFlight build 3906.** A patch: serve's unauthenticated file
routes stop handing out the PII key, raw transcripts and the run log, the
server answers only to loopback hosts (DNS rebinding) and its cookie only to
its own navigations, the static report escapes its embedded JSON, and
Re-analyse reaches the report (the project-condition reducer). `main` was red
before the run on two defects from that same evening — two platform `skip`s
over the ratchet, and a test driving a threaded re-import against the
in-memory `StaticPool` database — both fixed first. Run 60 min start to tag,
21 of them the `.dmg` rsync. Full account: `docs/release-log.md` § 0.31.5.

**0.31.4 shipped 28 Sep 2026, overnight — tag `v0.31.4` on `b80fdc31`,
TestFlight build 3870.** A patch of five fixes from one real project folder: a
silent audio track no longer comes back from mlx-whisper as "Thank you." every
30 s (large-v3-turbo's `no_speech_prob` is always 0.0 — `bristlenose/stages/CLAUDE.md`
§ Stage 5), word timings are joined to transcript paragraphs by time rather than
list position, the last paragraph's glow lasts to the end, a project with a lost
folder grant offers Locate…, and the Welcome shelf's resting covers stop showing
through each other. **The run went clean end to end in 32.5 min, preflight to
tag** — a third of the plan table's 1 h 57, because build-all now reuses the
preflight's resolve; the estimates are owed a re-measure. `Mac Build` was red
on CI from 26 to 28 Sep — an environment defect, not a product one: the runners'
1024×768 screen clamped the sidebar-fit harness's windows (fixed `15df357d`, see
`desktop/CLAUDE.md`). The harness then exposed a real column-stranding race
(`s22c`), fixed in `2129553e` and `6b126377` (a hide within 1 s of the logic's
own write is a late report of it). Full account: `docs/release-log.md` § 0.31.4.

**0.31.3 shipped 27 Sep 2026, overnight — tag `v0.31.3` on `9b1e4d84`,
TestFlight build 3793.** The re-drop release: dropping a folder the project
already held copied every recording again and paid to transcribe it again, and
the two copies became two participants whose identical quotes clustered as
corroboration. Also the Signals scroll model, the heatmap bar, sidebar folder
expansion and the projects column. **The release is the story, not the
payload.** It had already run once on 24 Sep and skipped its whole irreversible
block — which still printed `✓ every act is done`, so `main` sat bumped to
0.31.3 with no tag while the website advertised a version PyPI 404s, for two
days. Meanwhile CI went red on `main` on its own: SQLAlchemy 2.1.1 shipped and
`ext.asyncio` now raises without `greenlet`, where 2.0 installed it as an
ordinary dependency — nothing in the tree changed. Under that, mypy sat two
over its ceiling, reddening `ratchet`. Full account: `docs/release-log.md`
§ 0.31.3. Owed: **incident 22 is reopened** — a skipped irreversible step must
not satisfy the completion checklist — and mypy now has **zero margin** at
149/149.

**0.31.0 shipped 22 Sep 2026, overnight and unattended — tag `v0.31.0` on
`8b525e42` at 00:21Z, TestFlight build 3764.** The language release:
recordings are transcribed in the language they were spoken in (the default
had been *pinned* to English on every channel since January, and on the Mac
the UI language was being fed to Whisper as the spoken language), section and
theme names are generated in the researcher's language, the five framework
codebooks were re-read against their authors with in-place migration of
installed rows, and the Mac menu bar and Welcome screen stopped speaking
English. **The headline is that a soft gate found the release's worst bug and
two hard gates had been red all release with nobody downstream of them.** mypy
was two errors over its ceiling; one of the two was a `ValueError` that kills
any run reaching it (`transcribe_sessions` returning a 2-tuple from a 3-tuple
signature, reachable whenever a sidecar subtitle parses to nothing), invisible
to 5,247 green tests. `ratchet` and `inventory` had failed on every CI run of
the 178 commits. Four incidents, two of them a **new** recurring shape — *a
verdict that is about a commit, applied after the commit moved*: a fix
committed between attempts was never pushed because `push-main` is skipped on
resume, and `build-all` was skipped the same way over a `.pkg` built at the
previous commit, which would have shipped the App Store build and the `.dmg`
from **different commits**. Fixed at the cause: the test bundle now builds
beside the app (an Xcode signing race that 0.30.0 had papered over with
`xcodebuild clean`, which is why it recurred immediately), and push-main
re-pushes when HEAD is not published. Full account: `docs/release-log.md`
§ 0.31.0 and `docs/release-premortem.md` incidents 28–31. **Both pieces of
structural work that line used to name are now built** (24 Sep, verified 26 Sep):
dependencies resolve **once**, in preflight, with the lanes reusing that venv
(`84b8a742`, `2be60bf2` — `build-sidecar.sh --keep-venv`, and a new `inventory`
step), and the moved-HEAD guard is generalised from `strict-ci` to the class
(`scripts/release.sh`, `case "$id" in build-all|build-dmg)` → `pending` with
"HEAD moved since the artefact was built"). Left here as a worked example of
this file's own rule: **an owed item is a claim about the tree exactly as a
resolved one is** — three other docs still carried the first of these as owed
when it had shipped.

**0.30.0 shipped 21 Sep 2026, overnight and unattended — verified 9 of 9 channels by 07:08 BST.** The
Signals release: the Analysis lens is Signals on every surface (labels, route,
package, API, CSS, symbols, locale namespace, website), generation-4 signal
cards, CLI-only PII redaction end to end, the Codebooks focus cursor, ⌘F, one
keychain. **The release machine failed four times before it built, three of
them latent** — an unsigned test bundle in DerivedData, the sidecar re-resolving
24 dependencies *after* the drift gate had looked (a recurrence of 0.27.0 #5), a
relative `CODE_SIGN_ENTITLEMENTS` that the Settings package could not resolve,
and a comment of mine that truncated the archive command. Two of those were
green under tests that could not fail. Three gates and a resume guard came out
of it, all mutation-proved; `--yes` was already there and now appears on the
resume hints. Full account: `docs/release-log.md` § 0.30.0 and
`docs/release-premortem.md` incidents 23–27. Its one piece of structural work —
resolve dependencies once, in preflight — was **built on 24 Sep 2026**; see the
0.31.0 paragraph above.

**0.29.1 shipped 31 Aug 2026, evening — verified 9 of 9 channels.** A patch,
and a regression in 0.29.0's own headline feature: only one codebook could be
switched off at a time, because the new navigator sent a single-key patch to a
replacement endpoint — every write deleted every other codebook's state row,
and each wiped row could start an unrequested catch-up AutoCode run. The
navigator now sends the whole disabled set and mirrors it into SidebarStore
(the second half: other lenses read the switch from there, hydrated once per
session). Three tests pin the payload — the thing nothing had ever asserted;
see Gotchas, "Deleting a UI surface can orphan the test that was pinning a
wire contract". The release ran the day the evening rule learned about **bank
holidays** (working day, not weekday — check gov.uk/bank-holidays.json, don't
derive), and surfaced two release-machine defects, both fixed the same night:
the bump step's `git diff --quiet` guard could not see a STAGED bump (it
announced a commit it never made — an un-bumped push, saved only by an
unrelated failure), and `run` could discover a missing credential four steps
in — credentials are now resolved, probed and displayed above the one typed
confirmation (fingerprint pins, per-type keychain policy, announced dialogs,
caffeinate; the five-agent audit is in `docs/design-release-machine.md`).
Copr hit the Source0 CDN race even with `needs: verify-pypi` — the fetch now
re-asks a 404 for ten minutes, and the wheelhouse arch pin from the morning
held on an aarch64 builder.

**0.29.0 shipped 31 Aug 2026** on all nine channels — PyPI, GitHub Release,
Homebrew, Snap, TestFlight (build 3067), the notarised `.dmg`, the website
changelog, and Fedora Copr. It is the codebook release: the lens rebuilt as a
navigator with a browsable library, and three false claims corrected (the
uninstall dialog promising preserved AutoCode results, `pipx install
bristlenose` yielding a CLI whose `run` exits 1, and the privacy page denying a
server that exists). It also retired the v1 codebook lens — `CodebookPanel` and
its sidebar are deleted, `Tab.codebookV2` is out of the enum, and the lens took
`tag` back from the temporary `tag.square`.

Two release-machine defects surfaced during the run; both are fixed on main.
**A single negative ASC read was treated as proof of absence** — the TestFlight
probe asked App Store Connect seconds after a successful upload, got an empty
list because the build index had not propagated, and offered to re-upload a
build number that is spent forever. Only Apple's own `DUPLICATE` refusal
stopped it, which is luck rather than a gate; `BN_PROBE_WINDOW_S` now re-reads
across the propagation window. **And the Copr wheelhouse inherited the
builder's architecture** — see the Fedora paragraph below.

**Entitlements — the standing guard, rewritten 12 Sep 2026 because every clause of it had gone stale.** It read: *do not let the `associated-domains` entitlement ride — it is `skip-worktree`, so `git status` cannot see it; committing it obliges regenerating the Mac App Store profile or the archive fails to sign, and it is for a parked feature.* What is true now:

- **`Bristlenose.entitlements` is no longer `skip-worktree`.** That flag hid the parked `associated-domains` edit — and it hid the app-group addition too, silently: `git status` said clean, every test passed reading the working tree, and a fresh clone would have built a store binary with no app group and no error (the `c837f8b5` class). Flag cleared. `BristlenoseDebug.entitlements` carried it too until 29 Sep 2026, when it gained the team app group for the native MCP helper and the flag was cleared there as well — audit with `git ls-files -v | grep "^S"`.
- **`associated-domains` is in no entitlements file**, and its App-ID capability was **switched off in the portal on 12 Sep 2026**. That matters mechanically: while the capability was on, the profile authorised it, so a stray entitlement would have *signed fine* and shipped — the guard's own tripwire was dead. With it off, the archive fails to sign again, which is the behaviour the guard wants. Cloud-import does not need it: `ASWebAuthenticationSession(url:callbackURLScheme:)` handles the OAuth callback (`docs/design-cloud-import.md:541`).
- **The MAS build now legitimately carries one app group**, `group.app.bristlenose`, for Background Assets. The Developer-ID `.dmg` must **not** — Apple will not authorise an app group on that channel and it does not need one. Both channels build `Release`, so the split is a `CODE_SIGN_ENTITLEMENTS` override in `build-dmg.sh`'s archive invocation.
- **This is now gated rather than remembered**: `tests/test_entitlements_split.py` asserts the split, that the two files differ by exactly that one key, that the override sits inside the archive invocation, and — reading `git show HEAD:` rather than the filesystem — that the committed plist carries the group and the file is not skip-worktree again.

**Fedora/Copr — LIVE since 28 Aug 2026**, serving 0.29.0 from `cassiocassio/bristlenose` (fedora-43-x86_64 only; F42 was dropped by Copr). Install is `sudo dnf copr enable cassiocassio/bristlenose && sudo dnf install bristlenose` — proven on a clean F43 box before the docs went live (marker → `rpm`, man page rpm-owned with no home copy, `ffmpeg-free` serving, both SPA halves present). Rebuilds are automatic: `trigger-copr` in `release.yml`, **`needs: verify-pypi` never `publish`** (Source0 is fetched from PyPI during the build and would race the CDN). Standing obligations from `docs/design-fedora-packaging.md` §7: **CVE tracking for the vendored wheelhouse is ours forever** (`dnf` cannot see inside it), and **the wheelhouse tracks Fedora's Python on Fedora's calendar** — `.copr/Makefile` pins `python3.14` so a chroot move fails loudly, but a human still edits the line. The Copr API token (repo secrets + `~/.config/copr`) expires **23 Feb 2027**; the channel is live now, so the answer at the expiry alert is RENEW.

**The SRPM job's architecture is not the chroot's, and is not stable.** Copr
schedules the `make_srpm` stage wherever it likes: 0.28.0's ran on x86_64,
0.29.0's ran on **aarch64** against the same fedora-43-x86_64 chroot, and
`pip wheel` — which builds for whoever runs it — produced a `linux_aarch64`
wheelhouse. Pure-Python wheels are arch-agnostic and resolved fine, so the
failure surfaced inside mock as `Could not find a version that satisfies the
requirement pyyaml>=6.0 ... (from versions: none)` — the first dependency with
a compiled extension, and a message that names nothing about architecture.
**`from versions: none` rather than a version conflict is the tell**: the
package is there and no wheel is *compatible*. Nothing in the tree had changed.
`rpm/make-srpm.sh` now pins with `pip download --platform manylinux_*_x86_64`
in two passes — `pysrt` is sdist-only on PyPI and `--only-binary=:all:` refuses
it, so it is built locally first, where being pure Python makes it
`py3-none-any` and correct for every arch — and asserts afterwards that no
foreign-arch wheel reached the wheelhouse (`musllinux` named explicitly, being
x86_64 with the wrong libc). The fix is proven, not merely green: the rebuild
landed on aarch64 again and produced x86_64 wheels. **And verifying a Copr publish has
two ways to read as "the build produced nothing", both false.** The result
directory lists **no `.rpm` at all** — Copr stopped putting them there, and the
known-good previous build is the control that proves it is normal, not a defect;
the authoritative records are `<build-dir>/results.json` and the repo metadata
under `repodata/`, which is what a `dnf` client actually reads. And the listing
is served behind a redirect, so a `curl` without **`-L`** greps an empty
redirect body and reports no files, with no error. Confirm a publish by reading
`repomd.xml` → `primary.xml.gz` for the `<location href=...>` and then a `HEAD`
on the RPM itself — a build's own `succeeded` flag is not evidence the artefact
is fetchable.

**Nothing is owed from 0.27.0.** The Catalan native pass was **closed 24 Sep 2026** — the reviewers are in Mallorca and there is no trip before 2027, so `ca` rests machine-seeded alongside the other ten, which is a resting state and not a gap. Two things the closure does *not* discharge, both recorded in `docs/design-i18n.md` §Future locales: the glossary was never ratified, so it is an assembled table and not an authoritative one; and the glossary-first experiment it existed to run is **unresolved, not refuted**. The Welcome AI cell's hardcoded `Setup →` was **closed in `7f8f2645` + `89b11f5a`** and this line went on claiming it for days: the call site reads `i18n.t("desktop.welcome.aiSetup") + " →"`, the key is in all 21 full locales carrying Apple's own per-locale verb, and `zh-Hant-HK` is correctly absent because it inherits `zh-Hant`. Left as a worked example of the trap in Gotchas: **an owed item is a claim about the tree, exactly as a resolved one is** — verify by reading the line it names (`git log -S` on the string) before spending a cycle re-deriving finished work. **`v0.26.0` was tagged and abandoned** — it pointed 34 commits behind real work; it reached no channel and is in no changelog. Treat it as a version that never existed.

**Recent releases, in one line each** — **0.28.0** the Export-HTML button that worked only in the Mac app, and exported reports halved (3.38 → 1.55 MB) by embedding one language instead of 22; **0.25.0** the Sessions responsive grid and spatial arrow navigation; **0.24.0** Focus Mode and the single appearance seam (`AppAppearance.swift`); **0.23.0** the assistant surface end to end (`/mcp` on both channels, the `.mcpb` extension, Settings ▸ MCP Agents). Full entries in [CHANGELOG.md](CHANGELOG.md) — kept there rather than mirrored here, because a version history in two places is a version history wrong in one. React migration complete (Steps 1–10); bundled-sidecar desktop is the primary distribution path; CLI ships on PyPI + Homebrew + Snap + Fedora Copr. Static render is a sealed byproduct.

See [CHANGELOG.md](CHANGELOG.md) for version history, [TODO.md](TODO.md) for active work, and `git log` for the unabridged story.
