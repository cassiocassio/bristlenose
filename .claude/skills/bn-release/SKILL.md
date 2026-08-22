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
| **hard** | a PyPI version is burned forever | **approving the publish job** in GitHub's UI | unrecoverable: that version can never be re-used |

**Pushing the tag is on neither line.** The `pypi` environment carries a
required-reviewer hold, so `release.yml` runs its (strict-macOS) CI and then its
publish job *waits* — up to 30 days — for an approval on the run page. That is
what lets the tag go out at the start, with `main`, while everything is still
abandonable: to walk away, don't approve, and delete the tag. The preflight's
`publish hold` line proves the hold exists — **if it warns, you are in the old
world where a tag push publishes immediately, and the order below is wrong.**

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

```
1  bump + commit + tag    ./scripts/bump-version.py minor|patch     (or --build-only)
                          git add CHANGELOG.md README.md CLAUDE.md
                          git commit -m "bump to X.Y.Z"
                          git tag vX.Y.Z           ← AFTER the commit
                          verify: git rev-parse HEAD == git rev-parse vX.Y.Z^{}

2  push main AND tag      git push origin main
                          git push origin vX.Y.Z
                          Two commands back to back — never one `--tags` (debounce).
                          Publishes NOTHING: release.yml fires, runs CI with
                          strict macOS, and its publish job HOLDS on the pypi
                          environment gate. Two CI runs are now in flight.

3  Mac artefacts          run WHILE both CI runs execute — builds only, no uploads
                          SIGN_IDENTITY="Apple Distribution: Martin Storey (Z56GZVA2QB)" \
                            desktop/scripts/build-all.sh            ~35 min warm / ~50 cold
                          desktop/scripts/build-dmg.sh              ~30 min, one notary wait

4  THE GATE               both CI runs green — the main push run AND the release
                          run (whose macOS cells are blocking) — and every Mac
                          build gate green. Nothing irreversible has happened yet.
                          Any red: don't approve, delete the tag, fix, start over.
                          Cost so far: nothing.

5  uploads                desktop/scripts/upload-testflight.sh      ← SOFT irreversible
                          desktop/scripts/upload-dmg.sh             ← public permalink swaps

6  approve publish        GitHub run page ▸ Review deployments ▸ Approve
                                                                    ← HARD irreversible
                          Cascade: PyPI → verify-pypi · GitHub Release · Homebrew.
                          Then → new-release SKILL.md Step 6 for the PyPI verify.

7  website deploy         only AFTER PyPI confirms — see below
8  Snap                   gh workflow run snap.yml --ref main       (edge)
                          gh workflow run snap.yml --ref vX.Y.Z     (stable, Tier 2)
9  Tier 2 only            App Store submission, phased release on
```

**Step 1 owns bump, commit and tag as one unit.** `bump-version.py` no longer
tags at all (it can't be right — the commit the tag belongs on doesn't exist when
it runs), so the tag is yours to create *after* the commit. Verify tag == HEAD
before moving on. Do **not** delegate this to `/new-release` Step 4: that step is
the same bump, and after step 1 the tree already satisfies its publish-pending
case, whose instruction is *"push the existing tag"*. Its Step 6 (PyPI verify)
is the only piece you borrow, after the approval.

**`SIGN_IDENTITY` is not optional.** Unset, it defaults to `-` (ad-hoc), and
`build-all.sh` then silently skips the identity check, the provisioning-profile
check and the notarytool check — six gates off, no warning, and you find out 35
minutes later at the upload. `build-dmg.sh` needs no such care: it defaults to
the Developer ID identity and refuses ad-hoc outright.

**Why the tag goes out at the start.** The old order held the tag back because
pushing it *was* publishing — so the Mac lane ran first, and its uploads landed
before the tag run's CI verdict existed. That is the window 0.25.2 died in:
first CI run green, uploads out, second CI run red, three channels shipped on a
version the suite then rejected. With the publish hold, the tag is just a ref:
pushing it early starts the second CI run — the one whose macOS cells actually
block — while the Mac build runs, and **every** irreversible act now sits behind
both verdicts. Same failure today costs: nothing. The two runs are also two
*independent* samples of the suite on the same commit, which is precisely the
evidence a single green cannot give you on a flaky test.

**Budget cold, not warm.** A version bump invalidates the PyInstaller and
frontend caches, so the sidecar rebuild inside `build-all.sh` runs ~19 min rather
than ~6. A full Publish-tier release is **~1h55 wall-clock** under this order —
the second CI run overlaps the Mac build instead of following it.

**If approval never comes, nothing happens** — the run waits up to 30 days, then
expires un-published. An abandoned release is: don't approve, delete the tag
(`git push --delete origin vX.Y.Z && git tag -d vX.Y.Z`), fix, re-tag. The only
residue is a tag that briefly existed on origin.

**The website deploys last.** Its changelog page renders live from `CHANGELOG.md`,
so deploying before PyPI accepts the upload publishes a page announcing a version
nobody can install. Deploy is manual (rsync, SSH agent) — the maintainer runs it;
you prepare the content. And `build.py` does not copy `assets/`, so
`rsync -a assets/ build/site/assets/` before previewing a CSS or JS change.

If a step fails, say which command failed and where its log is. **You are a
conductor, not a wrapper** — every step must remain runnable by hand.

## Phase 6 · Verify by asking, never by remembering

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

---

## Rules

- **Never bypass a script's internal gate.** If `check-pkg-shippable.sh` refuses,
  the answer is to fix the artefact, never to work around the check.
- **A partial release is a normal outcome**, not an error. PyPI can succeed while
  Homebrew's poll times out. Report per-channel truth, not one verdict.
- **Weekday releases land after 9pm London; the landing act is the publish
  approval.** Pushing `main` and the tag publishes nothing (the hold), building
  publishes nothing — so the run can *start* any time, and only the approval
  waits for the window. Weekends unrestricted. It is a guideline — confirm
  rather than refuse. (A morning approval after an overnight run is a common,
  sanctioned override: the human is choosing the moment with full information,
  which is what the guideline exists to protect.)
- **Every upload spends its build number forever.** A replacement needs
  `./scripts/bump-version.py --build-only`.
- **Do not author the changelog alone.** Draft it; the human decides what users
  are told. That is the whole point of the version being their call.
