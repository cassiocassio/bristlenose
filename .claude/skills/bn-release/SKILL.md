---
name: bn-release
description: Orchestrate a release across all channels — TestFlight, .dmg, PyPI, GitHub Release, Homebrew, Snap, App Store. Runs the mechanical preflight, drafts the changelog and website updates against the diff, then executes in irreversibility order. Wraps /new-release rather than replacing it — that skill remains the CLI-publish specialist and owns the tag-surgery knowledge.
disable-model-invocation: true
user-invocable: true
allowed-tools: Bash, Read, Edit, Write, Glob, Grep, AskUserQuestion
---

Ship a release across some or all channels. Design: `docs/design-bn-release-skill.md`.

**Relationship to `/new-release`:** it owns the CLI publish (bump → tag → push →
PyPI verify) and carries the tag-surgery decision tree learned the hard way —
including the publish-pending case and when to `gh run rerun --failed` versus
move the tag. This skill does **not** restate any of it; Phase 5 hands off by
reference. One canonical home per piece of knowledge — a second copy is how the
two would drift, and it would drift in the part you only read at 11pm.

Use `/new-release` directly when the CLI is all you're shipping. Use this when
the Mac channels or the website are involved, which is most of the time.

**What you can and cannot do.** The scripts own every irreversible act and each
carries its own precondition internally — you cannot skip a gate, and must not
try. Your unique contribution is the **prose**: drafting the changelog and the
website updates against the diff, and judging whether they say the right thing.
Those judgements are **advisory** — they inform the human, they never block a
release, and they never wave through a mechanical failure.

---

## Phase 1 · Intent

```bash
git describe --tags --abbrev=0
git log $(git describe --tags --abbrev=0)..HEAD --oneline
```

**Three possible acts. Establish which one this is, first:**

| | What it is | Version | Prose |
|---|---|---|---|
| **Release** | You are telling users something is different | bumps | required |
| **Rebuild** | Refreshing TestFlight/`.dmg` with nothing new to say — e.g. the 90-day expiry | `--build-only` | none |
| **Nothing to ship** | The range touches no shipped code | none | none |

**Check the third one first, because it is cheap and it is common.** A week of
docs, tooling and CI work produces a long `git log` and an empty diff where it
counts:

```bash
git diff $(git describe --tags --abbrev=0)..HEAD --stat -- bristlenose/ frontend/
```

Empty means the wheel would be **byte-identical** to the version already on PyPI,
and the house rule applies: repo-only changes re-use the existing tag rather than
bumping. Say so and stop — do not manufacture a release to have something to do.
(Mac artefacts are a separate question: `desktop/` changes can warrant a rebuild
even when the wheel is unchanged.)

**The version is a communication decision and it belongs to the human.** Do not
infer it from the diff. A month of refactoring can be invisible to users; one
sentence in an LLM prompt re-judges every analysis anyone runs. Never say "this
looks like a patch because only Python changed" — which languages moved is
irrelevant to whether someone needs telling.

Summarise what landed, in user-facing terms, then ask: *minor (a capability was
added) or patch (fixes only)?* House rule: any user-facing feature → minor.

Then the tier — three, by audience:

- **0 · Due diligence** — CI only. Not this skill; it happens on every push.
- **1 · Cohort** — TestFlight · `.dmg` · PyPI · GitHub Release · Homebrew · Snap edge.
- **2 · Public** — Snap **stable** · **App Store**. Promotes a build that has already
  soaked on TestFlight. Nothing new is built.

Default to Tier 1. Ask before assuming Tier 2 — it is a different decision with a
different audience.

## Phase 2 · Preflight — read-only, always runs

```bash
./scripts/check-release-ready.sh <target-version>
```

That is the mechanical half and it is authoritative: **if it exits non-zero, stop
and fix, whatever your own reading says.** It checks tree, version agreement
across four files, changelog format and non-emptiness, tag, PyPI immutability,
certs, profile expiry, ASC config, CI status.

**Three rows are new (23 Aug 2026) and each replaces a paragraph this skill used
to carry as prose** — a warning to a reader about a condition a script can
assert is a missing gate, not a documentation problem:

- **`shippable diff`** — Phase 1's nothing-to-ship test, which this skill called
  "cheap and common" and nothing ever ran. It distinguishes a real release from
  a desktop-only rebuild from nothing at all.
- **`dependency drift`** — `THIRD-PARTY-BINARIES.md` against the resolved set.
  Warns here; `build-all.sh` step 2b still hard-fails later. Moves discovery of
  a major arriving mid-release ~40 minutes earlier, into the free step.
- **`publish state`** — is a run *currently* waiting on the pypi approval.
  Distinct from the existing `publish hold` row, which proves the gate exists.

**Expect it to fail on this first run, and do not treat that as a stop.** On a
genuine release the CHANGELOG and README entries for the target version cannot
exist yet — Phase 3 is where you write them. So the shape is **preflight → prose
→ preflight**, and only the second run's verdict is the gate. Any *other* failure
is a real stop. Three of its lines deserve a read rather than a skim: `git tag`
compares the tag to HEAD (diverged-and-unpublished is the dangerous state and
fails); `CI status` distinguishes green from in-progress from no-evidence; and
`publish hold` proves the pypi environment's required-reviewer gate exists —
**a warning there means a tag push publishes immediately, and Phase 5's
ordering does not apply until the hold is restored.**

Then do the part it cannot — read `git log <last-tag>..HEAD` **and the diff**, and
report:

1. **Does the CHANGELOG entry describe what actually shipped?** Name features
   present in the diff and absent from the entry. "Bug fixes" over a
   feature-bearing range is the failure to catch.
2. **Did new user-facing surface reach all three doc surfaces?** New CLI flags or
   commands must appear in `README.md`, `man/bristlenose.1`, and the website's
   `docs-src/cli.md`.
   ⚠️ Normalise roff escapes before diffing the man page or every flag reads as
   missing: `sed 's/\\-/-/g'` then strip `\fB`-style font escapes.
3. **Does the website still describe the product?** Homepage feature rows drift
   and nothing trues them — check them against what now exists.

Report these as findings with their evidence. They are advisory.

## Phase 3 · Draft the prose

This is the work most likely to be skipped at 9pm, and it is why this is a skill.
**Draft; the human edits.** Never publish prose they have not read.

- **`CHANGELOG.md`** — house format `**X.Y.Z** — _8 Aug 2026_` (em dash, italic
  date, no leading zero). Then the same entry in `README.md`'s changelog section.
- **Website** (separate private repo) — `docs-src/cli.md` for CLI surface, install
  instructions if install mechanics changed, homepage rows if the pitch moved.
  The changelog page needs nothing: `build.py` renders it live from `CHANGELOG.md`.
- **Tier 2 only — App Store "What's New"**, written for strangers rather than for
  the cohort. Different audience, different register.

## Phase 4 · The plan, and one authorisation

Present a single page: ordered steps, wall-clock estimates, what is being skipped
and why, and any advisory finding the human is choosing to accept.

**Mark both lines where reversible becomes irreversible — there are two, and they
cost differently:**

| | Line | Crossed by | Cost of being wrong |
|---|---|---|---|
| **soft** | a build number is spent forever | `upload-testflight.sh` | recoverable: `--build-only` and rebuild. But the build **reaches cohort testers** and cannot be recalled, only expired in ASC |
| **hard** | a PyPI version is burned forever | **pushing the tag** | unrecoverable: that version can never be re-used |

**Pushing the tag IS the hard line, since 23 Aug 2026.** The `pypi`
environment's required-reviewer hold was removed, so `release.yml` now runs to
completion on a tag: `publish` needs `build` needs `ci`, and `ci.yml` is invoked
with `strict-macos: true`. A tag push therefore publishes as soon as the full
matrix, e2e and strict macOS suite pass on the tagged commit.

**The gate did not go away; it stopped being a click.** At the old approval
moment every fact was already mechanical — both CI runs, the artefact's
signature and staple, `tag == HEAD`, the version not already on PyPI — and a
human clicking Approve at 11pm re-verified none of them. The preflight's
`publish gate` row now asserts the `publish → build → ci(strict)` chain and
**fails** if it is ever broken.

**Consequence for the order: the tag goes LAST.** After the Mac uploads, after a
strict verdict. `ci.yml` exposes `strict-macos` on `workflow_dispatch`, so that
verdict is obtainable on `main` without a tag — which is what keeps the 0.25.2
lesson intact (every verdict before every irreversible act) now that the tag is
the act that publishes.

Publishing the `.dmg` sits between the lines — technically re-publishable, but
the public permalink swaps the moment it lands, so treat it as audience-reaching
too. "Reversible" and "nobody saw it" are different properties; say which you
mean.

Ask **once**, before the *soft* line — not before the hard one. Everything up to
and including the pushes is genuinely abandonable and needs no ceremony.

Then ask **once**. Not per channel — a prompt per step trains people to say yes.
Declining here is the dry run; there is no `--dry-run` flag because the preflight
always ran.

## Phase 5 · Execute — least permanent first

Order matters and is derived from reversibility, not convenience.

```bash
./scripts/release.sh plan <X.Y.Z>
```

**That prints the ordered steps, and it is the only place they live.** This
section used to carry the table too, and a step order in two documents is a step
order wrong in one of them — the failure `docs/design-release-system-audit.md`
§6.4 calls *"knowledge quadruplication: drift between copies is unpredictability
on a delay."* The estimates in it are **measured** from `docs/release-log.md`'s
0.27.0 entry rather than guessed, and the consequence of each irreversible step
is printed immediately before that step rather than announced on a page where
nothing happens.

`scripts/test-release-sh.sh` pins the table's structural invariants: exactly
three irreversible steps, every one naming its cost, no reversible step claiming
one, the CI gate preceding all three, and the HARD line last. Both were proven
to fail on injection — moving the gate after an irreversible act is the 0.25.2
shape, and it is caught.

**`release.sh` has no `run`, deliberately.** It is the read-only half: `plan`,
`verify`, `status`, `abandon`. Executing the release is still yours and this
skill's, because the driver is gated on evidence
(`docs/design-release-machine.md` §12). What follows is the reasoning the table
cannot carry.

                          release, from probed numbers not memory
```

**Step 1 owns bump, commit and tag as one unit.** `bump-version.py` no longer
tags at all (it can't be right — the commit the tag belongs on doesn't exist when
it runs), so the tag is yours to create *after* the commit. Verify tag == HEAD
before moving on. Do **not** delegate this to `/new-release` Step 4: that step is
the same bump, and after step 1 the tree already satisfies its publish-pending
case, whose instruction is *"push the existing tag"*. Its Step 6 (PyPI verify)
is the only piece you borrow, after the approval.

**`SIGN_IDENTITY` is not optional — and since 23 Aug 2026 the script enforces
that rather than this paragraph.** It used to default to `-` (ad-hoc), which
silently skipped the identity, provisioning-profile and notarytool checks: six
gates off, no warning, discovered 35 minutes later at the upload. `build-all.sh`
now **refuses to start** with it unset (exit 2, immediately), and a deliberately
unsigned local build must say `SIGN_IDENTITY=-`, which reports the skipped gates
as a warning rather than saying nothing. The accident fails; the intent works. `build-dmg.sh` needs no such care: it defaults to
the Developer ID identity and refuses ad-hoc outright.

**Why the tag goes LAST.** It went first for eight days, and that was correct
while the hold existed: pushing it was just a ref, it started the strict CI run,
and every irreversible act sat behind two verdicts. With the hold gone the tag
publishes, so leaving it first would put the single unrecoverable act *before*
the strict verdict — worse than the 0.25.2 order it replaced.

Moving it last would normally reintroduce that same window from the other side:
the Mac artefacts would ship before any strict verdict existed. `ci.yml`'s
`workflow_dispatch` + `strict-macos` input is what closes it — dispatch the
strict run on `main`, wait for it, upload, then tag. Two independent strict
samples of the suite still land before anything irreversible: the dispatched one
before the uploads, and the tag's own before PyPI.

**Budget cold, not warm.** A version bump invalidates the PyInstaller and
frontend caches, so the sidecar rebuild inside `build-all.sh` runs ~19 min rather
than ~6. A full Publish-tier release is **~1h55 wall-clock** under this order —
the second CI run overlaps the Mac build instead of following it.

**Abandoning a release is now: do not push the tag.** Everything before it —
the bump, the commit, `main`, both builds, even the TestFlight and `.dmg`
uploads — is either reversible or merely audience-reaching, and none of it is on
PyPI. If the tag is already pushed and its CI is still running, deleting it
(`git push --delete origin vX.Y.Z && git tag -d vX.Y.Z`) cancels the publish
only if you win the race; assume you will not. `./scripts/release.sh abandon
<X.Y.Z>` prints the recipe **and** the website consequence, which is the part
that was previously remembered rather than printed.

**The website deploys last.** Its changelog page renders live from `CHANGELOG.md`,
so deploying before PyPI accepts the upload publishes a page announcing a version
nobody can install. Deploy is manual (rsync, SSH agent) — the maintainer runs it;
you prepare the content. And `build.py` does not copy `assets/`, so
`rsync -a assets/ build/site/assets/` before previewing a CSS or JS change.

If a step fails, say which command failed and where its log is. **You are a
conductor, not a wrapper** — every step must remain runnable by hand.

## Phase 6 · Verify by asking, never by remembering

```bash
./scripts/verify-channels.sh <X.Y.Z> [--abandoned <X.Y.Z>]
```

**That script is this table, executable** — seven channels, every probe
tri-state, exit 0 only when all of them are on the version. Run it rather than
running the rows by hand; the table below is now its documentation, not its
substitute.

**The rule it enforces, which the prose form could not:** *a successful probe
wins; an unsuccessful probe wins over nothing.* `curl` writes `000` on a
connection failure and `gh api` returns empty on expired auth — folded naively,
either reads as "not published" or, worse at the approval gate, as a network
fault reading as a human approval. Unreachable is its own verdict and is **not**
ok.

Pass `--abandoned <version>` whenever a tag was abandoned this cycle. 0.27.0's
real website failure was the live changelog naming **0.26.0** — a version that
never published — while the download served 0.27.0; a presence-of-target probe
passes the moment the target appears and would not have caught it.

No state file. Probe each channel; re-running this skill is therefore the resume
mechanism, and the resume path gets exercised every run rather than only in
emergencies.

| Channel | Ask |
|---|---|
| PyPI | `curl -s -o /dev/null -w '%{http_code}' https://pypi.org/pypi/bristlenose/X.Y.Z/json` → 200 |
| GitHub Release | `gh release view vX.Y.Z` |
| Homebrew | the tap formula's sdist URL names `bristlenose-X.Y.Z.tar.gz` |
| TestFlight | `xcrun altool --build-status --delivery-id <uuid> …` — **capture the UUID into the plan when `upload-testflight.sh` prints it**; it is the one probe you cannot reconstruct later |
| Snap | `curl -s -H 'Snap-Device-Series: 16' https://api.snapcraft.io/v2/snaps/info/bristlenose` — read `channel-map[].version` per channel. Public, unauthenticated, works fine from macOS; `snap info` is the CLI for the same data, not the only way to it |
| **Website** | `curl -s https://bristlenose.app/docs/changelog.html \| grep -c 'X\.Y\.Z'` → non-zero |
| `.dmg` | `curl -sI https://bristlenose.app/dmg/Bristlenose.dmg` → 302 to the versioned name |

**Probe the website even though its deploy is manual.** *Manual* and
*unverifiable* are different properties, and conflating them is how the only
channel nobody checks stays unchecked. It is in fact the **strongest** probe
available: that page renders from `CHANGELOG.md` at build time, so a hit proves
the deploy ran *after* the entry existed. Only that one page carries a version —
homepage, docs index, `cli.md` and the install page carry none, and the homepage
links the stable `/dmg/Bristlenose.dmg` redirect rather than a versioned
filename, so there is nothing else to drift.

Every row must trace to a command you actually ran. If you could not run one, say
so and name what would run it — never let a channel's status rest on someone
having told you.

**And "I can't probe this" is itself a claim that must be checked.** The Snap row
used to say the workflow conclusion was the only probe available on macOS,
because `snap` is not installed here. That was false: the store has a public
unauthenticated API, and it answers the question the workflow cannot. **A missing
CLI is not a missing channel** — nearly every store, registry and CDN in this
release has an HTTP endpoint behind whatever tool normally reads it, which is
exactly why the PyPI, Homebrew and `.dmg` rows are already `curl`. Before writing
"no way to check from here", spend one request finding out. Caught by the
maintainer, 22 Aug 2026, in a close-out table that had already declared the
limitation as fact.

**The two Snap probes answer different questions and Tier 2 needs the second.**
The workflow's `publish-edge` conclusion says the *upload* succeeded; the store
API says what is actually *released on a channel*, which is the thing a user
gets. They diverge for real: edge read `0.25.3 rev 9` for several minutes after
the run reported its build job green. For Tier 1 the run conclusion is a
reasonable interim signal — say it is interim — but the release is not verified
until `channel-map` names the new version. For Tier 2, where the whole act is
promoting an existing revision to `stable`, the store API is the *only* probe
that means anything.

Close with a table of what is now true per channel, plus the expiry clocks —
**`.dmg` 30 days from the *build*, TestFlight 90 from the *upload*.**

## Phase 7 · Log it

**Append an entry to `docs/release-log.md`.** Started 22 Aug 2026 at the
maintainer's request, to run for the next few releases and then be judged on
whether it earned its keep. Read the file's header before writing — it states the
three questions the log exists to answer, and an entry that answers none of them
is noise.

Do this **after** Phase 6, so every number in it is one you probed. Commit it with
the release, not later: a log written the next morning is a log written from
memory, which is the failure mode it exists to prevent.

Five sections, and the third and fourth are the ones with value:

1. **What shipped** — two or three sentences. Not the changelog; a pointer plus
   whatever the changelog cannot say, such as a version that was abandoned.
2. **Timing** — one row per phase. **Mark each measured or estimated, and split
   out any wall-clock spent waiting on a human.** Without that split the averages
   slowly come to describe how fast the maintainer answers questions. Compare the
   total against the skill's own estimate and say where the gap went.
3. **Builds** — every attempt, not just the one that worked. For each failure:
   what gate caught it, the real cause, the fix's sha. A gate that fires on a
   real defect is the system working and belongs in the record as much as a
   clean run does.
4. **Tricky things** — the section the maintainer asked for by name. Anything
   that cost a cycle, misled you, or would mislead the next reader: a tool
   whose output lies, a check that cannot see what it claims to check, an
   assumption that turned out unverified. **Write the tell, not just the fix** —
   the next person meets the symptom before they meet the cause. If a trap here
   has now appeared twice across entries, that is the signal to build a gate for
   it, and say so in the entry.
5. **Skill changes provoked by this release**, and **what is owed** out of it.

**The log is evidence, so let it contradict the skill.** If the measured timings
keep beating the plan table's estimates, change the estimates. If a step never
fails, consider whether its ceremony is earned. If a trap recurs, it has stopped
being a trap and become a missing gate. A release log that only ever agrees with
the skill is one nobody is reading.

---

## Rules

- **Never report a step's outcome from a background task's exit code.** Redirect
  to a file, read the file, quote its verdict line. A backgrounded
  `build-all.sh … | tail` reports **`tail`'s** status, not the build's: on
  0.27.0 all five build and upload runs reported exit 0 and **three had failed
  outright**, printing `✗ Build failed`. Reading the notification instead of the
  log would have carried three failed builds forward as successes. The scripts
  already do this correctly internally (`upload-testflight.sh:202` redirects and
  reads `$?`); the pipe that lost the verdict was **yours**, one level up. Same
  rule `CLAUDE.md` already states for pytest, and it applies to every step here.
- **Never bypass a script's internal gate.** If `check-pkg-shippable.sh` refuses,
  the answer is to fix the artefact, never to work around the check.
- **A partial release is a normal outcome**, not an error. PyPI can succeed while
  Homebrew's poll times out. Report per-channel truth, not one verdict.
- **Releases land after 9pm London on a working day; the landing act is the TAG PUSH.**
  Weekends and UK bank holidays: any time (check `gov.uk/bank-holidays.json`,
  don't derive the date).
  Since 23 Aug 2026 there is no approval to wait on — the `pypi` required-reviewer
  hold was removed, and `publish → build → ci(strict-macos)` is what now stands
  between a tag and PyPI. Pushing `main` and building still publish nothing, so
  the run can *start* any time; only the tag waits for the window. Weekends
  unrestricted. It is a guideline — confirm rather than refuse. (A morning tag
  after an overnight build is a common, sanctioned override: the human is
  choosing the moment with full information, which is what the guideline exists
  to protect.)
- **Every upload spends its build number forever.** A replacement needs
  `./scripts/bump-version.py --build-only`.
- **Do not author the changelog alone.** Draft it; the human decides what users
  are told. That is the whole point of the version being their call.
