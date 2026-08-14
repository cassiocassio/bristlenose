---
status: current
last-trued: 2026-08-14
trued-against: the shipped uploader (upload-testflight.sh + check-pkg-shippable.sh, two live uploads: 0.25.1/2450, 0.25.3/2472)
---

# Scripted TestFlight upload — the gate, then one command

> **Truing status:** As-built record (trued 2026-08-14). Everything this doc
> planned as Phase 1/2/3 shipped — `check-pkg-shippable.sh`,
> `upload-testflight.sh`, `test-check-pkg-shippable.sh` — and has uploaded two
> real builds. The plan text is preserved; §As-built delta below records the
> five places reality diverged from it. Originally a proposal replacing the
> "drag the `.pkg` into Transporter.app" step; revised after a six-agent review
> pass (the first draft was roughly twice this size and built the wrong thing —
> §Problem records why).

## Changelog

- _2026-08-14_ — trued up: status proposed → as-built (all three phases shipped,
  two live uploads); added §As-built delta (five divergences incl. the D4
  half-wire); recorded the 14 Aug escalations (unparsed UUID fatal, UNCONFIRMED
  exit 1, BN_SKIP_ASC_VALIDATE announced skip) and closed §Open question the
  other way; de-duplicated the 90-day-refresh paragraph and corrected its
  bump-version claims (--build-only exists; the script no longer tags at all);
  fixed the --api-key/--apiKey spelling. Anchors:
  `desktop/scripts/upload-testflight.sh`, `desktop/scripts/check-pkg-shippable.sh:364-376`,
  commits "make the checks that couldn't fail, fail", "stop paying Apple twice:
  one notary round trip, one 675MB transfer", "bump-version: --build-only, and
  check the tag before writing anything".

- _2026-08-07_ — Phase 0 split: the ASC API turns out to be opt-in per team behind an
  Account-Holder **Request Access** gate with no committed approval SLA. Recorded the two
  escapes (Phase 1's gates are entirely offline; `altool`'s app-specific-password path
  needs no API access) so the request's latency never sits on the critical path.
- _2026-08-06 (post-review)_ — halved. The founding premise ("the `.dmg` channel is better
  engineered, copy its shape") was wrong and is corrected below. Cut: the Keychain
  credential mechanism, `--validate-only`, `--dry-run`, the `--upload` flag, the
  delivery-ID two-step, the CI phase, and D5's build-number pre-flight. Added: the two
  gates matching rejections this project actually took, and negative fixtures.
- _2026-08-06_ — initial draft.

## Problem

`build-all.sh` runs ten steps and seven verification gates, then **printed** (until
"build-all: point the footer at upload-testflight.sh, not Transporter"):

```
next   drag into Transporter.app, or: xcrun altool --upload-app -f Bristlenose.pkg …
```

Everything up to that line was scripted, gated, and logged. The one step that was
irreversible and outward-facing — putting a build on Apple's servers under our name — is a
GUI drag with no precondition and no record. And it recurs: TestFlight builds expire 90
days after upload (build 2068 from 14 Jul expires ~12 Oct), so keeping a cohort testing
means re-uploading forever. Manual steps that recur are the ones that rot.

**The premise the first draft got wrong.** It argued that the Developer-ID `.dmg` channel
is "better engineered than the primary one" and that the fix was to copy its shape.
That reasoning doesn't survive contact with why `upload-dmg.sh` is elaborate: it pushes
644 MB over a domestic uplink to a shared host we administer, where a truncated write
serves a broken image to strangers at 2am, where retention is nobody else's job, and
where a stable URL has to be repointed atomically. **Apple's channel has none of that.**
Apple owns the destination, checksums the transfer, imposes no quota, and no stranger
can download a half-written file.

So the two channels are not the same problem wearing different hats, and importing
`upload-dmg.sh`'s machinery here is the wrong abstraction. The operational tell was
already visible in the first draft: making its credential story fit a second caller
needed a flag, a temp file, and a `trap`. That was the diagnostic, not a wrinkle.

**What actually transfers is one lesson, not a shape.** From
`check-dmg-shippable.sh`'s header, written after a complete, correctly-sized 0.24.0 `.dmg`
sat on disk for 14 hours looking finished while `spctl` called it `rejected — Unnotarized
Developer ID`:

> This gate exists to make that unpublishable rather than merely detectable, so it is
> called as a PRECONDITION INSIDE `upload-dmg.sh` — not as a sibling step an operator
> can forget on the one night it matters.

The near-miss had a second cause worth carrying: two of that script's four gates were
written `cmd && ok "passed"`, and `set -e` deliberately exempts the left operand of `&&`,
so a failure printed nothing and fell through to the success banner. **Every assertion
here uses `|| die`, never `&& ok`.**

**Correct shape for this channel: a gate, and one command.** Not a channel.

## What `altool` actually does (probed, 26.40.1)

| Need | Command |
|---|---|
| Dry run against Apple's own validator | `altool --validate-app <pkg>` |
| Upload **and wait for processing** | `altool --upload-package <pkg> --wait` |
| Auth | `--apiKey <KEYID>` / `--apiIssuer <ISSUER>` (camelCase — the hyphenated spellings in an earlier draft don't exist; see the transcript below) |

Three corrections to the first draft, all from reading the tool rather than assuming:

- **`--upload-package`, not `--upload-app -f`.** The man page treats the former as primary,
  `--delivery-id` is documented as its return value, and `--wait` is documented **only**
  on it. `build-all.sh`'s footer advertised the wrong spelling — fixed; the footer now
  points at `upload-testflight.sh` and carries no altool invocation at all.
- **`--upload-package --wait` collapses the proposed two-step.** No separate
  `--build-status --delivery-id` call, no status-parser, no delivery-ID plumbing.
- **`--build-status` cannot enumerate builds.** It takes a build number as *input*
  (`--delivery-id`, or `--apple-id` + `--bundle-version` + `--bundle-short-version-string`
  + `--platform`). There is no "latest build for this version" query and no listing verb.
  The first draft's D5 was written against a command that doesn't exist.

`--validate-app` is the highest-value single item in this plan. It runs App Store
Connect's server-side validation **without delivering a build** — the same checks that
produced three nested-signing rejections on 14 Jul, discoverable in a minute instead of
after a 223 MB upload.

**No new dependency.** The third-party ASC CLI stays unadopted.

## Decisions

**D1 — Local script. Not CI.** The repo's grain already is this: CLI channels (PyPI, Snap,
Homebrew) run in CI; desktop channels run as local scripts. CI would mean the Apple
Distribution private key in Actions secrets — a cert that can sign malware distributable
to every Mac — plus porting a build that depends on a machine-local `.venv-sidecar`,
Homebrew toolchain, gitignored ffmpeg binaries, and a 447 MB bundle with 219 inner
Mach-Os to sign. That's cost, not posture. Revisit if the Mac ever stops being the only
place a build can happen; bus factor is the real trigger, not a second developer.

**D2 — Do NOT flip `destination` to `upload` in `ExportOptions.plist`.** The tempting
one-liner: `xcodebuild -exportArchive` would upload directly. It uploads *before* gates
7–10 run, inverting the precondition lesson. Second reason: `uploadSymbols` only takes
effect on the `destination=upload` path, so flipping it silently changes symbol behaviour
too. Recorded because someone will propose it.

**D3 — The `.p8` is a `0600` file at `~/.private_keys/`, excluded from Time Machine.**

The first draft routed the key through Keychain and materialised it to a trap-cleaned
temp file, because "secrets go in Keychain" is the right Mac instinct. It was wrong here,
and its own text conceded why: once `/usr/bin/security` is granted "Always Allow", the
delta against a `0600` file is approximately zero against the threat model that matters
(code execution as the user), and zero against the one FileVault covers (stolen laptop,
powered off). What it bought instead was a materialisation path, a `trap`, a temp file a
`kill -9` leaves behind, and a ⚠ warning about whether the store round-trips its own
secret. A mechanism that needs a warning label about its own correctness is the design
review, not a task.

The one measured objection survives and is met by an assertion rather than a mechanism:
`~/.appstoreconnect` would be **Time-Machine-Included**, so a plaintext key would land in
every hourly snapshot, retained for months, possibly onto an unencrypted external.
`tmutil addexclusion` closes that in one Phase 0 line, and Phase 1 asserts
`tmutil isexcluded` with a `|| die`.

`~/.private_keys/` specifically — it is one of altool's own four search paths, so no
`--p8-file-path` plumbing is needed, and being home-rooted it can't intersect the repo.
Deleting the mechanism also deletes a finding it created: the first draft's Phase 0
stored the key with `security add-generic-password -w "$(cat …)"`, putting the PEM body
in argv **and permanently in shell history** — the exact exposure D3 had rejected
`--auth-string` for.

Still add `private_keys/`, `*.p8`, `AuthKey_*` to `.gitignore`: altool's *first* search
path is `./private_keys`, resolved against CWD, which for a script run from the repo root
is the repo root. That is a public repo and a submission-capable key.

**Credential scope: mint with the `Developer` role, not `App Manager`.** Developer can
upload builds and query build status; App Manager additionally grants store-metadata
editing and submit-for-review, which nothing here uses. Use a **Team Key** (issuer
required), not an Individual Key — an Individual Key inherits the creating user's role,
which for the Account Holder is maximal. A two-minute re-mint makes trying the narrow
role free.

**D4 — The gate is a re-runnable script the uploader cannot run without.**
`check-pkg-shippable.sh <pkg-path>`, called by both `build-all.sh` and
`upload-testflight.sh`. One implementation, not two that drift.

**D5 — No build-number pre-flight. `--validate-app` already is one — confirmed live.**

The first draft proposed querying ASC to refuse a duplicate `(marketing version, build
number)` pair locally. Cut on review, on the argument that it would be a second
implementation of a check Apple already performs. **Verified 7 Aug 2026** — the very first
run of `check-pkg-shippable.sh` with a working credential, against the `.pkg` on disk:

```
ERROR (-19232): The bundle version must be higher than the previously uploaded
version: '2445'.  status: 409  code: ENTITY_ERROR.ATTRIBUTE.INVALID.DUPLICATE
meta: previousBundleVersion : 2445
```

Server-side, in ~24 s, on a 644 MB artefact that was never transferred. A local pre-flight
would have duplicated this exactly, using a query that doesn't exist, to save nothing.
**Do not reinstate it.**

Two things this run also proves, which Risk 2 previously listed as unverified: the
credential chain works end to end (JWT accepted, structured response returned), and
`--validate-app` exits non-zero with a legible, actionable reason — so the `|| die`
discipline has something real to bite on.

Worth knowing when the 90-day refresh comes round: ASC keys on
`(CFBundleShortVersionString, CFBundleVersion)`, so build numbers need only be unique
*within* a marketing version. The refresh problem this paragraph originally
recorded — `bump-version.py` couldn't produce a same-version build bump, and
re-running it at an existing version died on `git tag` after rewriting three
files — was fixed in two stages: `--build-only` shipped ("bump-version:
--build-only, and check the tag before writing anything"), and the script later
stopped tagging entirely ("stop bump-version.py tagging a commit that doesn't
exist yet"). `./scripts/bump-version.py --build-only` is now the documented
refresh path, and the uploader's own Undo text names it. _(An earlier revision
of this doc carried this paragraph twice, near-verbatim — an editing artefact,
collapsed 14 Aug.)_

## Plan

### Phase 0 — credentials _(human; blocking for the Apple round trip only)_

**0a. The API is opt-in per team, and the request is gated.** App Store Connect → Users and
Access → Integrations → App Store Connect API shows *"Permission is required to access the
App Store Connect API"* with a **Request Access** button until the **Account Holder**
enables it (checkbox to accept the API terms, then Submit). Apple documents these requests
as *"reviewed and approved on a case-by-case basis"* and commits to no SLA — **fire it
before you need it.** In our case (7 Aug 2026) approval was **instant**: the Team Keys /
Individual Keys tabs and the Generate API Key dialog appeared immediately on submit. Treat
that as one data point, not a guarantee; the escapes below exist for the other case.

**This does not gate the work.** Two escapes, both real:

- **Phase 1's local gates need no Apple credentials at all.** codesign, nested
  `app-sandbox`, framework `--identifier`, host sandbox, `ITSAppUsesNonExemptEncryption`,
  privacy manifests, the §2.5.2 PYZ scan, `pkgutil`, profile expiry — every one is offline.
  Only the closing `altool --validate-app` needs auth. Build the gate and its negative
  fixtures while the request sits.
- **`altool`'s other auth path skips this gate entirely.** `-u <apple-id> -p @keychain:<item>`
  — Apple ID plus an app-specific password, read natively from Keychain, no API access
  request needed. `--store-password-in-keychain-item` writes it. The existing
  `bristlenose-notary` profile is already this shape, so the pattern is on the machine.
  It is account-wide and unscopeable, so it is the **bridge, not the destination** — but
  it unblocks Phases 1–2 today and is a one-line swap when the key arrives.

**0b. Once access is granted:** generate a **Team Key** (the *Individual Keys* tab inherits
the creating user's role — for the Account Holder that is maximal) with the **Developer**
role. The `.p8` downloads exactly once and cannot be re-downloaded.

Prepare the destination **before** clicking Generate — there is no second chance:

```bash
mkdir -p ~/.private_keys && chmod 700 ~/.private_keys && tmutil addexclusion ~/.private_keys
```

Immediately **after** the download — and then *verify*, because a Finder move applies
`umask 022` and this silently produced a world-readable `644` key on the first real run:

```bash
mv ~/Downloads/AuthKey_*.p8 ~/.private_keys/ && chmod 600 ~/.private_keys/AuthKey_*.p8
ls -l ~/.private_keys/          # must read -rw-------, not -rw-r--r--
```

Capture into `desktop/scripts/.ship-local.conf` (gitignored, the `.dmg` uploader's existing
config channel) — none of these are secrets:

- `BRISTLENOSE_ASC_KEY_ID`, `BRISTLENOSE_ASC_ISSUER_ID`
- `BRISTLENOSE_ASC_APPLE_ID` — the app record's **numeric** ID. Needed by `--build-status`
  and `--beta-app-store-text`, and it is what stops altool *inferring* the app record from
  the bundle ID (see Risks 1). Find it via `altool --list-providers` → `--list-apps`.

**Backup: use the existing dotfiles mechanism, don't invent an obligation.** The house rule
is already written down — git is a sharing medium so `~/.gitignore_global` excludes all
cert material, while the nightly iCloud rsync **deliberately includes secrets** because
recovery from a dead Mac is its entire purpose (`.ssh/`, `.gnupg/`, `.aws/` are already in
its `PATHS`). A `.p8` is the same class as an SSH private key, so it belongs there too:

- add `".private_keys/"` to that script's `PATHS`
- add `*.p8` to `~/.gitignore_global` — it lists `*.pem` / `*.key` / `*.p12` /
  `*.provisionprofile` but **not** `*.p8`, so every repo on the machine is exposed until
  it does

`tmutil addexclusion` above is belt-and-braces for a future Time Machine disk (none is
configured on this Mac today) — it is **not** the backup story and must not be mistaken
for one. Excluding the key from TM while forgetting to add it to the dotfiles rsync leaves
it backed up by nothing, which is exactly what happened on 7 Aug 2026.

**Then, before writing any script: run `altool --validate-app` by hand, once, against the
current `.pkg`, and once against a deliberately broken one.** Phase 2 gets written from
that transcript, not from this document. Everything below the gate is currently designed
against an unrun tool.

### Phase 1 — `check-pkg-shippable.sh <pkg>` _(the actual deliverable)_

Takes a path, exits 0/1/2, every assertion `|| die`. This is ~80% of the value and is
shippable independently of any uploader.

**It is not a lift.** Today's gates c–f read `$EXPORTED_APP`, which under `method=app-store`
is the `.app` from the **xcarchive** — `build-all.sh:335-348` falls back to it and prints a
`note:` saying so. So the gates have never once touched the `.pkg` payload, and
`check-dmg-shippable.sh`'s load-bearing lesson (*interrogate the copy the recipient
receives*) describes a gap that exists in this channel **right now**. Phase 1 changes the
subject deliberately; "behaviour-preserving" is the wrong success criterion.

Mechanism: `pkgutil --expand-full` into a trap-cleaned temp dir, assert exactly one `.app`
in the payload, gate that. **Spike first** — if extraction doesn't round-trip a signature
well enough for `codesign --verify --deep --strict` to mean anything, say so in a comment,
keep the local gates on the xcarchive `.app`, and let `--validate-app` be the authority on
the shipped bytes. Don't pretend either way.

Assertions, in cost order (local first, Apple's validator last):

- The seven existing gates — a–f **plus d2**; the first draft said "six" and the
  per-script README says "four". Three sources, three numbers. Make one authoritative here.
- **Nested-executable `app-sandbox`** — every Mach-O in the bundle. This was rejection #2
  on 14 Jul. Local `codesign --verify` passes without it.
- **Framework main binaries carry a real `--identifier`**, not an auto-derived
  `Python-<hash>`. This was rejection #3. `sign-sidecar.sh:183-209` implements the fix;
  nothing verifies the result.
- **Host `app-sandbox`** — the `ITMS-90296` auto-reject. Set correctly today
  (`project.pbxproj:515`); a gate is how you stop caring which doc is right about it.
- **`ITSAppUsesNonExemptEncryption` present** — set today (`:486`, `:531`). Delete that key
  and every other gate still passes while builds silently stop reaching testers, stuck in
  Missing Compliance. Textbook silent failure.
- **The §2.5.2 `itms-services` PYZ scan** (`check-sidecar-appstore-strings.sh`) re-run
  against the sidecar *inside the pkg*. It currently runs at step 2c against the source
  tree — fine inside one linear build, wrong under D4's premise.
- **`pkgutil --check-signature` asserting the leaf is `3rd Party Mac Developer Installer`**,
  not merely "trusted". A Developer ID Installer pkg satisfies today's looser test, and
  there is a live Developer ID channel producing artefacts in the same `desktop/build/`.
- **Provisioning profile expiry** — warn at T-30, fail at T+0. Mac App Store profiles
  expire annually; the current one's first anniversary lands inside the window this plan
  covers. An expired profile is the canonical evening-waster: the local archive succeeds
  and only ASC objects.
- **Credential hygiene** (D3), both assertions, because both have already failed once:
  `tmutil isexcluded ~/.private_keys` reports `[Excluded]`, **and** the `.p8` is mode
  `600`. On 7 Aug 2026 the key landed `644` — default `umask 022` — and was
  world-readable until caught. A `chmod` in a runbook is a hope; this is the check.
- **`altool --validate-app`** last, and **skipped with `bn_gate … skip` when
  `SIGN_IDENTITY="-"`** — step 10 runs on every build including ad-hoc ones, and an
  unconditional Apple round trip would fail every local build.

**Negative fixtures — `test-check-pkg-shippable.sh`, same commit.** The house bar is
already written at `test-upload-dmg.sh:16-17`: *every assertion is shown to FAIL on its own
violation, because a gate that can't fail is worse than no gate.* These gates have never
been shown to fail **and** they're changing subject, so a lifted gate that silently no-ops
on a `.pkg` would pass green forever. That is the `sidecar-source-hash.sh` class this
project has already eaten twice. Fixtures by file surgery on the artefact the build
already made: delete a `PrivacyInfo.xcprivacy`; `codesign --remove-signature` and ad-hoc
re-sign; strip an entitlement from one nested binary.

**~~Report nesting — resolve before writing.~~ Resolved as built — option 1:** the child logs to a file, the parent shows one line + the log path (`upload-testflight.sh:145-151`), and `check-pkg-shippable.sh` never sources `report.sh` at all. Original analysis: `build-all.sh` sources `report.sh` and calls
`bn_autowrap`, which exports `_BN_ACTIVE=1`; a nested child's `bn_check`/`bn_gate` emit
**nothing** (`report.sh:47-51`). So naively extracting the battery turns seven labelled
gate lines into one opaque step with no reasons on failure. `check-dmg-shippable.sh` never
hits this because `build-dmg.sh` doesn't render. Pick: child logs to a file and the parent
shows one line plus a path (the existing house pattern, `build-all.sh:76-92`), or teach
`report.sh` a child-replay protocol. The first is conventional; the second preserves the
report you'd miss.

### Phase 2 — `upload-testflight.sh <pkg>` _(write it from Phase 0's transcript)_

- Resolve config; exit 2 with a usage message if unconfigured (`upload-dmg.sh`'s contract).
- **Call `check-pkg-shippable.sh` as a precondition.** Not optional, not skippable.
- Print the local `(marketing version, build number)` pair and the delivery target.
- `altool --upload-package <pkg> --wait --api-key … --api-issuer … --apple-id …`.
- **Echo the delivery ID before entering the wait** *(shipped differently: the UUID is
  sed-parsed from the log AFTER altool returns — `upload-testflight.sh:211` — so a Ctrl-C
  mid-wait echoes nothing; the live log file named at upload start is the resume handle)*,
  so a Ctrl-C or a closed lid leaves a
  token to resume by hand. Print it on the failure path too.
- **Treat a zero exit as unverified; the terminal state is the verdict.** There is a
  documented Apple failure mode where altool exits 0, prints no error, and the build never
  appears in ASC — while ASC has registered the delivery, so a retry is then rejected as a
  duplicate. Parse the terminal state as an **allowlist**: an unrecognised state fails.
- On failure, print Apple's issue list **verbatim** — `build-all.sh:499-503` already does
  this for notarytool. A script that renders `ITMS-90238` as "upload failed" is strictly
  worse than the drag.
- No `--dry-run` (Apple's `--validate-app` *is* the dry run, server-side, against the real
  artefact; a local one prints your own script back at you) and no `--validate-only`
  (`check-pkg-shippable.sh <pkg>` already is that verb).

Also: `build-all.sh` step 6 gains one `cp` to a versioned filename
(`Bristlenose-<MARKETING>-<BUILD>.pkg`). The export dir is `rm -rf`'d at the top of every
run (`:278`) and the artefact is named `Bristlenose.pkg`, so "upload a `.pkg` from an
earlier build" currently has no earlier build, and resolving by the unversioned name is
exactly what `check-dmg-shippable.sh` rule #1 exists to forbid. One line; don't import
`--keep N` retention with it.

### Phase 3 — the footer _(one line)_

Replace `build-all.sh:609` with `bn_art "next" "desktop/scripts/upload-testflight.sh <pkg>"`.

No `--upload` flag on `build-all.sh`. Upload isn't a step of the build — it's a separate
act with a separate credential and separate irreversibility, and a flag that's off in
every run is configuration for the configurable.

Demote Transporter to the **failure** path rather than deleting it (see Risks 1). When the
uploader dies, the last line the operator reads should be the manual route that still
works.

## What stays manual

- **Minting the key** (Phase 0) — Apple portal, once.
- **"What to Test" notes.** `--beta-app-store-text` exists but needs the numeric app ID,
  a prescriptive `up-<appleID>/<platform>/…` folder layout you're expected to `--download`
  and rebuild, `--bundle-version` (undocumented in `--help`, documented in Apple's bundled
  `AppStoreText-README.md`), and pre-existing Beta App Information. For a five-person
  internal cohort this is a Slack message.
- **Beta App Review** — external TestFlight only.
- **Apple's processing time** — waited on, not eliminated (planned budget was 10–60 min; measured ~2.5 min on both live uploads — see §Observed contract).
- **Tester group assignment.** Internal TF auto-distribution is an ASC per-group
  checkbox ("Enable automatic distribution"), not a platform guarantee, and the script
  cannot observe it.

## Risks

1. **altool on Xcode 26 has live app-record-resolution bugs.** The rewrite *infers* the app
   record from the bundle ID and has been reported picking the wrong one (fastlane #29698),
   and failing outright with `-19237` (#29820) — in one Apple Forums case (812132)
   Transporter uploaded the same artefact correctly where altool and the REST API both
   misrouted it. Bristlenose is partly insulated (one app record, no prefix siblings), but
   the mitigations are cheap: pass `--apple-id` explicitly so nothing is inferred, document
   `--use-old-altool` in the script header, and keep Transporter on the failure path.
2. **~~Nobody has run altool once.~~ RETIRED 7 Aug 2026 — the full chain ran.** Build
   0.25.1 (2450) went from `build-all.sh` through the gate to TestFlight. See §Observed
   contract below. Residual: altool **silently ignores unknown flags** — a typo'd option
   produces no complaint, so the script must validate its own argv. *(As built: the three
   tempting flags are refused explicitly with an explanation; anything else falls to the
   file-exists check on arg 1 — covered for the one argument it takes.)*
3. **~~Phase 1's pkg expansion may not round-trip signatures.~~ SETTLED 7 Aug 2026 — it
   does.** `check-pkg-shippable.sh:17-21` records the verification: `pkgutil
   --expand-full` round-trips the signature intact.
4. **The extraction can make a gate decorative.** `bn_gate`/`bn_check` only *report* — each
   is preceded by its real `if`. When the block moves, the tempting tidy-up is
   `cmd && bn_gate x ok "…"`, which is `fc1d6ca7` in a new costume and invisible because the
   report still renders. Make the rule mechanical, not remembered:
   `grep -nE '&& *(ok|die|bn_gate|bn_check) ' desktop/scripts/*.sh` as a build gate.
5. **Verified only through a pipe.** `bn_autowrap` re-execs with stdout piped, and a 10–60
   min `--wait` with progress output is exactly where the TTY and piped paths diverge. Give
   the long-wait path one bare, un-piped run before believing it.
6. **`~/.private_keys/AuthKey_*.p8` is submission-capable.** Mitigations: `0600`, home-rooted
   (can't intersect the repo), Time-Machine-excluded, Developer role, revocable in one
   click. No rotation cadence is defined — annually, or on any suspected exposure.

## Observed contract — the real transcript (7 Aug 2026, build 2450)

Phase 2 gets written from this, not from the man page. Measured, not inferred.

**Upload.** `altool --upload-package <pkg> --type macos --apiKey … --apiIssuer … --wait`
transferred 674,984,926 bytes in 8.11 min (1.4 MB/s), then printed:

```
UPLOAD SUCCEEDED with no errors
Delivery UUID: b819212d-f037-472a-a25d-ebacf9fac824
```

**`--wait` polls at 30 s.** `Upload is in state 'PROCESSING'. Checking again in 30 seconds…`
× 5, then a terminal block. **Processing took ~2.5 min, not the 10–60 the plan budgeted** —
one data point, don't over-fit, but the wait is far shorter than feared.

**Terminal payload — the fields worth parsing:**

```
PROCESSINGSTATE: VALID          IMPORT-STATUS: VALID
IS-ON-APP-STORE-CONNECT: true   BUILD-AUDIENCE-TYPE: APP_STORE_ELIGIBLE
VERSION: 2450                   EXPIRATION-DATE: 05/11/2026
EXPIRED: 0                      USES-NON-EXEMPT-ENCRYPTION: false
```

**Parse `PROCESSINGSTATE` as an allowlist** (`VALID` passes; anything unrecognised fails).
`IS-ON-APP-STORE-CONNECT: true` is the field that answers the documented
exit-0-but-the-build-vanished failure, and `EXPIRATION-DATE` is the 90-day clock the whole
plan exists to service — print it in the footer rather than computing it.

**Confirm independently; don't take altool's word for it.** A separate
`altool --build-status --delivery-id <uuid>` returned `BUILD-STATUS: VALID` +
`IS-ON-APP-STORE-CONNECT: true`. That call is cheap, needs no artefact, and is the
mitigation for Risks 1 and the vanished-build case — Phase 2 should make it a step, not
an optional nicety. It also proves `--build-status` works fine with an API key (unlike
`--list-providers`, which is Apple-ID-only).

**Do NOT pass `--show-progress` when stdout isn't a TTY.** It emits `\r`-overwritten bars
that turned an 11-line log into 131 KB of noise, which is exactly the pipe-vs-TTY trap
already in the house gotchas. Gate it on `[ -t 1 ]`.

## Open question

> **Settled 14 Aug 2026 — the other way.** The leaning below was toward running
> `--validate-app` on *more* paths; it now runs on **fewer**. Measured cost
> decided it: on the upload path the gate's validate shipped the same 675 MB to
> the same endpoint that `--upload-package` revalidates minutes later — ~8 min
> and ~10% of a release's wall clock to learn the same answer. The uploader now
> passes `BN_SKIP_ASC_VALIDATE=1` (announced skip, `check-pkg-shippable.sh:364-376`);
> a standalone gate run keeps validate-app and remains the documented dry run.
> `build-all.sh` never gained the every-build validate. Commit: "stop paying
> Apple twice: one notary round trip, one 675MB transfer".

Original question, preserved: Should `--validate-app` run on every release build, not just
before an upload? It costs a network round trip and catches the ITMS-class rejections
early. Leaning yes — but it needs the ad-hoc skip above, so settle it once Phase 1 exists.

## As-built delta — what shipped differently from this plan

Trued 14 Aug 2026. Five divergences, none of which invalidate the plan's
reasoning; three are open gaps a future pass may still close.

| Planned | As built | Status |
|---|---|---|
| D4: `check-pkg-shippable.sh` called by **both** `build-all.sh` and the uploader — "one implementation, not two that drift" | Only the uploader calls it; `build-all.sh` still runs its own inline gates a–f/d2 against the **xcarchive** copy | **Open gap** — the drift D4 exists to prevent is structurally possible |
| D3 credential hygiene: assert `tmutil isexcluded` AND mode 600 | Only existence + a mode-600 *warning* in the preflight; no tmutil assertion anywhere | **Open gap** |
| Versioned `cp` in build-all step 6 (`Bristlenose-<ver>-<build>.pkg`) | Not shipped; uploader defaults to the unversioned export path, mitigated by the gate's pkg-vs-tree version check | **Open gap** |
| Delivery-ID echoed before the wait | Parsed from the log after altool returns; the log file is the resume handle | Shipped differently, acceptable |
| `&&-ok` grep as a build gate (Risk 4) | Never wired | **Open gap** (the class it guards was fixed by hand in `fc1d6ca7` and audited since) |

Shipped beyond the plan (14 Aug): an unparsed Delivery UUID is **fatal**; an
unconfirmed `--build-status` prints an **UNCONFIRMED** banner and exits 1 —
where non-zero does *not* mean the upload failed (the build number is spent
either way; the recovery is App Store Connect, never a re-upload); and the
gate's validate-app is an announced skip on the upload path
(`BN_SKIP_ASC_VALIDATE=1`). Commits: "make the checks that couldn't fail,
fail", "stop paying Apple twice".

## See also

- `desktop/scripts/check-dmg-shippable.sh` — the gate-as-precondition pattern and the
  near-miss that produced it
- `desktop/scripts/upload-dmg.sh` — a good uploader for a *different* problem; read
  §Problem here before copying it
- `desktop/scripts/README.md` — the per-script register; two new rows and a changed
  "Ship a TestFlight build" job, same commit
- [design-desktop-build-orchestration.md](design-desktop-build-orchestration.md) — how the
  `.pkg` gets built
