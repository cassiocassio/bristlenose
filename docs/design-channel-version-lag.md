---
status: proposal — investigation 9 Oct 2026, no code or public-doc change made; the recommendation needs the maintainer's decision
measured-against: PyPI JSON (upload times), `gh run list` for release.yml / snap.yml / windows-installer.yml, the GitHub Releases API, the homebrew-bristlenose tap's commit log, Copr's build API, the Snap Store info API, microsoft/winget-pkgs#449372, docs/release-log.md 0.27.0–0.36.0
---

# Channel version lag — what the public docs can honestly say

**The question (maintainer, 9 Oct 2026):** *does all this mechanic mean we are going
to get different time lags on versions when we release dmg, cli, App Store and
winget — public docs for v1.0.1 would be time-lagged per platform?*

**Short answer: yes, and they already are.** Today the lag is minutes for six of
the eight channels and was invisible because of it. Three channels are already
outside that band, though nothing says so. Homebrew's tap can be stale
indefinitely. Snap has no stable release at all. The website once ran two days
*ahead* of PyPI. winget and the Mac App Store will add lags measured in days, and
both can **skip** a version entirely. The docs site describes one version, the
newest, and nothing on it says which channel has that version yet.

The decision not to add a one-line "winget may lag" note stands. This doc is the
longer treatment that decision asked for.

Contents: §1 what was measured · §2 where the public surfaces name a version ·
§3 how other projects handle it · §4 options · §5 recommendation · §6 what this
does not settle.

---

## 1. The lag per channel, measured

Every number is labelled. **MEASURED** means read from an API or log for this
project. **INFERRED** means reasoned from documentation, release order, or one
data point. The window is **0.30.0 → 0.36.0** (21 Sep – 8 Oct 2026, 13
releases): the release-machine era, after the `pypi` approval hold was removed
on 23 Aug. Earlier tag→PyPI numbers (up to 705 min) measure a human clicking
Approve, not a channel, and are excluded.

The reference clock is **the tag push**, taken as the `createdAt` of the
release.yml run it triggered. The tags are lightweight, so their own dates are
commit dates and say nothing about when they were pushed.

### 1.1 The table

| Channel | Gets version N at | Lag from tag push | Label | Can it skip N? |
|---|---|---|---|---|
| **TestFlight** | upload, *before* the tag (`release.sh` order: Mac uploads → strict CI → tag) | **leads** PyPI; the upload step including Apple's processing (`altool --wait`) runs 387–479 s | MEASURED (`events.jsonl` step times, release-log 0.31.4–0.35.0) | Yes, in principle. One tester is enrolled, so nobody external waits |
| **`.dmg`** (bristlenose.app) | upload, before the tag; `upload-dmg.sh` repoints `/dmg/Bristlenose.dmg` and writes `/dmg/latest.json` in one step | **leads** PyPI by roughly the strict-CI span. 0.36.0's file carries `last-modified 22:46:37Z` and the tag run started at 22:46Z | INFERRED from the release order. Last-modified is the rsync'd mtime, so it gives an upper bound and not the upload time | Has: 0.25.2 reached TestFlight and the `.dmg` only |
| **PyPI** | `publish` job on the tag | **11.4–16.8 min** for 10 of 12 tag pushes, median **14.1 min**; 30.6 and 31.1 min for 0.31.1/0.31.2; 52.4 min for 0.31.0 (the tag moved once) | MEASURED (PyPI first-file `upload_time` minus run `createdAt`) | Only on a failed run. Five versions stalled silently in June |
| **GitHub Release** | `github-release` job, a sibling of PyPI | PyPI **+15–20 s** | MEASURED (`publishedAt`, 0.28.0–0.36.0) | No |
| **Homebrew tap** | `notify-homebrew` → the tap polls PyPI, then commits | PyPI **+19–79 s** to the formula commit | MEASURED (tap commit log, 0.30.0–0.36.0) | No. But see §1.2: the *user* may never receive it |
| **Fedora Copr** | `trigger-copr` (needs `verify-pypi`) → SRPM → mock build | PyPI **+10.2–14.2 min** to build end, 10 of 11; 28.7 min for 0.31.0. Failures: 0.29.0 +32 min, 0.28.0 **+5 h 20**, 0.31.1 **+11 h 22** (a manual rebuild each time) | MEASURED (Copr `ended_on`) | Not so far. A failed build that nobody re-runs would skip it |
| **Snap edge** | `snap.yml` dispatched `--ref main` at the tag | 0.36.0 released to edge at 23:03:28Z, **PyPI +2 min** (17 min after dispatch). 0.30.0: "published but not yet in the store map" 15 min after the tag, present 10 min later | MEASURED (Snap Store `released-at`, one point; release-log 0.30.0) | — |
| **Snap stable** | `snap.yml --ref vX.Y.Z` | **never.** The store's channel map holds `latest/edge` only, and no release has dispatched a tag ref | MEASURED (Snap Store info API, 9 Oct) | Every version so far |
| **Website** | `deploy.sh`, by hand, after PyPI answers | Minutes normally: 0.30.0 deployed ~2 min after PyPI's 200. **Ran two days ahead** for 0.31.3, when a deploy carried a changelog for a version that had stopped before its tag | MEASURED (release-log 0.30.0, 0.31.3) | n/a: it renders whatever `CHANGELOG.md` says |
| **Windows installer** on the GitHub Release | built on the tag by `windows-installer.yml` (dispatched 22:47Z), attached by hand | 0.36.0 asset uploaded **06:51:54Z, ~8 h** after the tag | MEASURED (one point; the gap was a human sleeping, not a machine) | Yes. It is a manual step |
| **winget** | a PR on microsoft/winget-pkgs → bot validation → moderator → merge | 0.36.0 PR opened 07:09Z, **~8 h 20 m** after the tag. **Not merged** at 07:22Z on 9 Oct. The new-package moderator queue is "days" | MEASURED (PR open time); the merge lag is unmeasured | Yes. A PR still open when N+1 ships is superseded |
| **Mac App Store** | App Review, then optionally a phased release | not live | INFERRED: review typically 1–2 days, plus up to 7 days of phased automatic updates if that is switched on | Yes. A version still in review when N+1 is ready gets withdrawn or skipped |

**What the table says in one line:** inside the release machine the spread is
the **~15 minutes** between the Mac uploads and Copr finishing. Outside it, three
channels run on a clock nobody here controls: winget's moderators, Apple's
reviewers, and the end user's own update cadence.

### 1.2 The lag after the channel: when the user actually gets it

A channel "having" N does not mean an installed copy updates. This half is
INFERRED from each tool's documented defaults; none of it was measured here.

- **Homebrew:** `brew upgrade` refreshes taps when `HOMEBREW_AUTO_UPDATE_SECS`
  allows (24 h by default). Bare `brew upgrade` **skips an untrusted tap
  altogether** (Homebrew 6.0; CLAUDE.md § Homebrew 6.0 tap trust). For any
  install that predates the trust caveat, the lag is *indefinite* and silent,
  and `bristlenose doctor`'s `check_brew_tap_trust` is the only thing that says
  so.
- **Snap:** snapd auto-refreshes about four times a day, and users can defer it.
  Edge users get N within hours.
- **Copr:** `dnf upgrade` honours the repo's `metadata_expire`. The Copr `.repo`
  file sets none (MEASURED: fetched 9 Oct), so dnf's default applies (48 h,
  INFERRED). An explicit `dnf upgrade --refresh` skips the wait.
- **pipx/uv:** nothing happens until the user runs an upgrade.
- **`.dmg`:** nothing auto-updates (no Sparkle, by decision). The old copy
  *expires* 30 days after its build. That forces an upgrade, but it is not an
  update channel.
- **TestFlight:** testers get new builds automatically.
- **winget:** `winget upgrade` finds N once the manifest has merged and the
  client has refreshed its source cache.

So even on channels with seconds of publish lag, the version a user is *running*
trails the version the docs describe by hours to weeks. That was true before
winget, and it is the larger effect.

### 1.3 Two findings from the measurement

- **The winget PR's first stall was our own manifest, not the queue.**
  `wingetvalidator-prod` reported a URL validation error on #449372 at 07:13Z:
  the manifest's `ReleaseNotesUrl`, `https://bristlenose.app/changelog.html`,
  had returned 404 since the website v2 cutover. The page is at
  `/docs/changelog.html`. A concurrent session fixed the template and the PR
  branch at 08:19 BST (`3493bac1`), and at 07:22Z the PR carried
  `Validation-Guide` only. It is a measurable lag cause all the same: it cost
  the first version about an hour before any moderator could look. (The CLA was
  signed at 07:14Z.)
- **README.md:69 links "Bristlenose.dmg" to GitHub's `releases/latest`, which
  has no `.dmg` asset.** The 0.36.0 release carries the man page, two SBOMs and
  the Windows installer. The `.dmg` is served from `bristlenose.app/dmg/`. This
  is the version-availability problem in its simplest form: a link that names a
  channel but does not point at the channel's own artefact.

---

## 2. Where the public surfaces name a version, and what each assumes

| Surface | Names a version? | How it gets it | What it assumes |
|---|---|---|---|
| `CHANGELOG.md` (also the website's `/docs/changelog.html`) | Every entry, `**X.Y.Z** — _date_` | Hand-written at bump time | That a version exists everywhere on the date given. The date is the bump/tag date. It already marks **surface** differences ("on the Mac", "This is the CLI only") and once marked a **channel** gap: 0.25.2, *"Reached TestFlight and the direct-download `.dmg` only"* |
| `README.md` changelog section | The last few entries, mirrored | Copied at release | Same as CHANGELOG |
| `README.md` install block | No version. It names channels (`brew`, `snap --edge`, `dnf copr`, `pipx`, `uv`) | Hand-written | That each command installs "the current" version. True to within minutes for brew/Copr/pipx; edge for snap is explicit |
| `INSTALL.md` | No version. It explains why snap needs `--edge` (no stable release yet) | Hand-written | The only surface that already states a channel's availability gap, and states it without a version number |
| `man/bristlenose.1` | `.TH … "bristlenose 0.36.0"` | `bump-version.py` | Self-consistent: the page ships inside the package it describes, so it is never ahead of its own install. The website's CLI page is a different surface |
| Website homepage (`content/index.html:492`) | The Mac button's version | **Fetched at view time from `/dmg/latest.json`**, which `upload-dmg.sh` writes in the same step that repoints the download | That this is the `.dmg`'s version, and it is. **This is the one surface already built the right way:** the channel reports its own version, and the typed `0.31.2` is only a fallback |
| Website footer (`site.js` `VERSION`) | `v0.36.0` on every page | `build.py` stamps the package version at deploy; `deploy.sh` refuses a mismatch | That the deploy happens after PyPI, which it normally does. 0.31.3 shows what happens when it doesn't |
| `docs-src/*.md` (install, windows, cli, feature pages) | No version numbers. A grep for `since/from/new in X.Y` finds none | Hand-written | That the reader runs the newest version. Feature pages describe current behaviour with no "added in" markers |
| Held drafts: `after-winget/first-version` (this repo), `after-winget` (website) | No version, but they make **winget the lead Windows route** | Waiting branches | That winget serves a version as soon as the docs say so. Their names follow neither each other nor `after-pypi/<version>`, and `release.sh verify` sees neither |

**So the version-bearing claims are few, and two of them are already solved.**
The man page is solved because it ships with what it describes. The homepage
button is solved because it asks its channel. The real exposure is not a version
number printed on a page. It is **behaviour described without one**: a feature
page that is true for N and false for the N−1 a winget or App Store user is still
running.

---

## 3. How comparable projects handle it

Researched 9 Oct 2026. VERIFIED means the source was read at the URL; INFERRED
means it wasn't.

| Project | Install docs name versions? | Says anything about lag? | Measured downstream lag |
|---|---|---|---|
| **GitHub CLI** | No | No. It splits channels into **official** (winget, Homebrew: "supported by the GitHub CLI maintainers") and **community** ("does not maintain… [no] guarantees of… availability"). [install_windows.md](https://github.com/cli/cli/blob/trunk/docs/install_windows.md) VERIFIED | v2.102.0: winget merged **~1h45** after release, homebrew-core **~4 h**. The last six winget updates took 1–2 h, one took 22 h. VERIFIED |
| **uv** | Only inside example installer URLs | No note across nine channels. [installation](https://docs.astral.sh/uv/getting-started/installation/) VERIFIED | 0.12.24: Homebrew ~2 h, winget ~4 h (PR filed by a third party). VERIFIED |
| **Ollama** | Only as a pinning example | No; points at the releases page. [linux](https://docs.ollama.com/linux) VERIFIED | winget updates filed by a third party, merged in 1–1.5 h. VERIFIED |
| **VS Code** | Per-version release notes carry their own downloads | Gradual rollout is announced **per feature**, not per build. [v1_141](https://code.visualstudio.com/updates/v1_141) VERIFIED | — |
| **Docker Desktop** | Per-version, per-platform download links in the notes | **One standing sentence:** "updates typically become available within a week of the release date". Platform items sit under *For Mac / For Windows / For Linux*. [release-notes](https://docs.docker.com/desktop/release-notes/) VERIFIED | — |
| **Tailscale** | One version for every platform | It names the platforms that ship **less often** (NAS; iOS stable is App Store only) and offers stable/RC/unstable **tracks**. The changelog uses per-platform headings. [versions](https://tailscale.com/kb/1168/versions) VERIFIED | — |
| **Node.js** | — | Package-manager packages "are not maintained by the Node.js project". [package-manager](https://nodejs.org/en/download/package-manager) VERIFIED | — |

**Channel mechanics that bear on this design (VERIFIED unless marked):**

- **winget:** a human moderator approves **every** PR, new versions included. Updates "may require less scrutiny when prior manifests provide clear precedent", and new versions and new packages sit in separate queues. A PR auto-merges once it is approved and validated, and it is published within an hour of the merge. Auto-merge for verified publishers has been an open request since 2022.
  - Sources: [Moderation.md](https://github.com/microsoft/winget-pkgs/blob/master/doc/Moderation.md), [FAQ](https://github.com/microsoft/winget-pkgs/blob/master/doc/FAQ.md), [#89190](https://github.com/microsoft/winget-pkgs/issues/89190).
  - **Peers' version updates land in hours.** It is INFERRED that ours will once the package is accepted. The days-long wait is the new-package queue.
- **Homebrew:** `HOMEBREW_AUTO_UPDATE_SECS` defaults to 86400. homebrew-core autobumps every 3 h, but our own tap doesn't need that because we push to it.
- **Snap:** snapd checks for updates 4 times a day, and a user can hold refreshes for up to 90 days ([manage-updates](https://snapcraft.io/docs/how-to-guides/manage-snaps/manage-updates/)).
- **dnf:** `metadata_expire` defaults to 48 h ([conf_ref](https://dnf.readthedocs.io/en/latest/conf_ref.html)).
- **App Store:** Apple reviews 50% of submissions in under 24 h and 90% in under 48 h ([app-review](https://developer.apple.com/distribute/app-review/)). A phased release spreads automatic updates over 7 days, and anyone can download manually at any point ([phased release](https://developer.apple.com/help/app-store-connect/update-your-app/release-a-version-update-in-phases)).

**Patterns.** Five strategies show up, and no project combines all of them:

1. **Install docs name no versions.** They name channels and link to each channel's own page.
2. **Channels are labelled by who maintains them, not by how far behind they run** (gh, Node).
3. **Gradual availability gets one standing, time-bounded sentence** (Docker), not a per-release note.
4. **One version number everywhere, with platform-specific items marked in the changelog** (Tailscale, Docker).
5. **Tracks instead of dates:** stable/RC/unstable, Insiders/stable, LTS/Current.

**No project found publishes a per-channel version table generated from the channels' APIs.** Bristlenose's homepage button, which reads `/dmg/latest.json`, is already a one-channel version of that.

---

## 4. Options

All three keep a single, unversioned docs site describing the newest release. A
docs site per version (`/v0.36/…`) was considered and dropped. None of the peers
does it for an app of this kind, and it would multiply the 41-page site by every
release, at 97 releases in 204 days. It would also not answer the question
anyway: a reader still has to know which version their channel serves.

### Option A — Version-free docs, channels described by cadence

The docs follow one stated rule and make no per-release claims.

- **Docs pages never name a version or say "new in X.Y".** The man page and
  CHANGELOG are the exceptions: one ships inside its own package, and the other
  is a list of versions by definition. This already holds, and A turns the
  habit into a rule (§2's grep finds no violations today).
- **A channel's availability gap is described once, as a standing property of
  that channel, not per release.** The model is `INSTALL.md`'s Snap paragraph
  ("no stable release on the Snap Store yet"). For winget, that would be a
  sentence written when the package first lands, in the shape of Docker's or
  Tailscale's: *new versions reach winget after Microsoft's review, usually
  within a day.* The text is the maintainer's call. **This is not the quick
  sentence that was declined.** That sentence would have been a disclaimer added
  to today's docs about a channel that is not live. This one describes a live
  channel's cadence on the page that tells you to use it, and only once that
  cadence has been measured.
- **CHANGELOG keeps marking surface differences ("on the Mac", "CLI only"), and
  marks a channel only when that channel will never get the version.** The
  0.25.2 line, "Reached TestFlight and the direct-download `.dmg` only", is the
  template.
- **The release machine changes as in §5.2, whichever option is chosen.**

*For:* it is what gh, uv, Ollama and Node do. Nothing on it can go stale on a
schedule. It costs a rule and one paragraph per slow channel.
*Against:* a winget or App Store user reading a feature page can't tell whether
their copy has that feature yet. The answer lives with the channel (`winget
show`, the App Store page) and `bristlenose --version`, not in our docs.

### Option B — A per-channel availability record, published

`release.sh verify` already probes every channel. Its result would be written as
`channels.json`: per channel, the version it serves, the time that was first
seen, and its state (`ok · pending · overdue · superseded · never`). The website
would fetch it at view time with `no-store`, as the homepage already fetches
`latest.json`, and render:

- one line per install route on the install page ("winget: 0.36.0");
- an availability line under each CHANGELOG entry on the website
  ("Not yet on: winget (in review)").

*For:* it answers the question exactly and no peer does it. It reuses probes
that already exist and a fetch pattern the site already uses. It updates without
a redeploy, so a winget merge three days later shows up on its own.
*Against:* it makes a public surface out of a probe. A probe error becomes a
public falsehood unless `unreachable` renders as "unknown", never as "not
available". Something has to re-run verify after the release night: a scheduled
job, or the maintainer. The channels.json publish needs the website's SSH path,
which only the maintainer's machine has. And it puts "pending" on show for
channels whose lag is nobody's fault.

### Option C — Lockstep: hold the announcement until every channel has N

The website deploy and the CHANGELOG/README entry wait until winget, and later
the App Store, have N.

*For:* nothing public is ever ahead of any channel.
*Against:* the docs then lag the fast channels by days, which turns the problem
around rather than solving it. PyPI, Homebrew and Copr users get N on the night
with no notes. If winget skips N, the hold never releases. And the 0.31.3
incident shows what the hold *mechanism* is like in practice: a deploy that
didn't know about the hold broke it. **Rejected.** It is listed because it is
the obvious first idea.

---

## 5. Recommendation

**Option A for the docs, the release-machine changes in §5.2 regardless, and
Option B left as a deferred possibility.**

### 5.1 Why A

The measurement settles most of the question. Inside the release machine the
whole spread is about 15 minutes, which is below anything a docs reader would
notice. The lags that matter are **after** the channel: the user's own update
cadence, an untrusted tap, snapd's four checks a day, dnf's 48 h cache. Those
existed before winget, they are larger than winget's, and no per-channel docs
note fixes them. winget's days are the **new-package** queue. Peers' version
updates merge in 1–4 h (§3), so "days" probably belongs to winget's first
version only (INFERRED; measure it on the second version before writing the
cadence sentence). The App Store adds 1–2 days of review. Peers handle both with
at most one standing sentence.

B is the more interesting option, and it is novel, but two things should come
first. The machine has to be able to say "pending" without lying (§5.2 builds
that). And it should be clear that a winget or App Store user has actually been
misled by docs that ran ahead. Nobody external is on either channel yet. Revisit
B when the App Store is live, because a 1–2 day review with optional phased
release is the first lag a real user will notice.

### 5.2 The release machine — needed under any option

**(a) `verify` gets a `pending` state, and slow channels become *followers*
outside the exit code.**

Adding winget to `CHANNELS` as it stands would be wrong:

- `rollup()` counts anything that isn't `ok`/`skipped` as failure, so `verify`
  would exit 1 for days.
- `release.sh run`'s exit 75 ("acts done, verification pending") would never
  clear.
- `held_for_version` would keep printing "verify has not passed yet" over
  `after-pypi` holds that are ready to land. Those holds are keyed to PyPI and
  would be blocked by a channel they have nothing to do with.

`project.conf` already handles the analogous case with `CHANNELS_UNPROBEABLE`.
The proposal:

```sh
CHANNELS="pypi github homebrew testflight dmg snap copr website"   # lockstep: the exit code
CHANNELS_FOLLOW="winget"            # later: mas. Reported, never in the exit code
FOLLOW_BUDGET_winget=72h            # first value is a guess; re-measured per version
```

A follower's probe reports one of five states:

| State | Meaning |
|---|---|
| `ok` | the channel serves a version ≥ N |
| `pending` | evidence that N is in flight (an open winget PR for N, an App Store version in review) and still inside the budget |
| `overdue` | in flight past the budget. Printed loudly, still outside the exit code |
| `superseded` | N never landed and N+1 is in flight or live. That is normal, not `bad` |
| `bad` | not in flight at all: nobody submitted N |

The rule `verify-channels.sh` exists to enforce still applies: **`pending` has
to be proved by a probe** (the PR exists and is open; ASC says *In Review*),
never assumed because time has passed. A follower that cannot be probed is
`unreachable`, exactly as a lockstep channel is today.

**(b) `after-pypi/<version>` generalises to `after-<channel>/<version>`, keyed
to that channel's own verdict, with ≥ semantics.**

- `after-pypi/<v>` keeps its meaning and its name. PyPI is the lockstep
  channel's proxy.
- `after-winget/<v>` lands when winget serves **≥ v**. The ≥ is needed: if
  winget skips v, a hold on v should still release when v+1 lands, not wait
  forever.
- `held_for_version` becomes `held_for <channel> <version>`. `verify` lists each
  channel's holds next to that channel's row and says *land these* as soon as
  **that** channel is `ok`, not when everything is.
- **The website repo has to be scanned too.** Today the held winget work sits on
  two branches with two different names, `after-winget/first-version` in this
  repo and `after-winget` in the website repo, and `release.sh verify` sees
  neither. The website path is already in reach: `deploy.sh` reads this repo's
  changelog by absolute path. A `WEBSITE_REPO` line in `project.conf` would let
  `verify` list the website's holds as well.
- The existing two branches would be renamed `after-winget/0.36.0` in both
  repos. With ≥ semantics, a "first version" hold is the same thing as a hold on
  the first version submitted.

**(c) The freeze is unaffected.** `release-freeze` holds `main` only while a
driver runs. Followers resolve days later, outside any run, so nothing freezes
for them.

### 5.3 What A asks of the maintainer, as decisions rather than edits

1. Adopt the rule "docs pages name no versions; channel gaps are standing
   properties". It holds today, so adopting it changes no file.
2. When winget's second version has merged, so its update cadence is measured,
   decide whether `INSTALL.md` / `docs-src/install.md` carry a cadence sentence
   for it, and what it says.
3. ~~Decide whether the README's `.dmg` link (§1.3) should point at
   `bristlenose.app/dmg/Bristlenose.dmg`, the channel's own artefact.~~
   **Done 9 Oct 2026, at the maintainer's request:** README.md:69 now links the
   permalink, which 302s to the current versioned `.dmg`. That is pattern 1
   from §3.

---

## 6. What this does not settle

- **The new-package wait is the only winget number we have, and it is not
  measured yet.** #449372 had only just cleared its own URL error when this
  was written (§1.3). The update lag after that is borrowed from gh/uv/Ollama.
- **Snap stable.** Every version so far has skipped the stable channel. That is
  a standing gap `INSTALL.md` already states, not a lag. Whether to start
  releasing to stable is a separate decision.
- **Homebrew's untrusted-tap users** are stale indefinitely, and no docs or
  machine change here reaches them. `doctor`'s check is the only remedy, and
  only for users who run `doctor`.
- **App Store specifics** (phased release on or off, how a version still in
  review interacts with the next one, whether the `.dmg` keeps shipping beside
  it) belong to the App Store channel's own design when it exists. This doc only
  reserves `mas` a place in `CHANNELS_FOLLOW`.
- **Option B's open questions:** who re-runs verify after release night, how
  `channels.json` reaches the site without the maintainer's SSH agent, and the
  rendering rule for `unreachable`. These get answered if B is picked up, not
  before.
- **Implementation.** Nothing in §5.2 is built. It touches `project.conf`,
  `verify-channels.sh` (a follower loop and `probe_winget`), `release.sh`
  (`held_for`), and both test suites (`test-verify-channels.sh`,
  `test-release-sh.sh`), whose canned-input pattern covers the new tri-state
  verdicts directly.
