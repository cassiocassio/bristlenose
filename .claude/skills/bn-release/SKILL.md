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
is a real stop. Two things the script cannot see, so check them yourself: whether
an existing tag points at HEAD (it only checks the tag exists), and whether the
CI line means "green" or merely "no evidence" — those read the same in its output.

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
| **hard** | a PyPI version is burned forever | pushing the tag | unrecoverable: that version can never be re-used |

Publishing the `.dmg` sits between them — technically re-publishable, but the
public permalink swaps the moment it lands, so treat it as audience-reaching too.
"Reversible" and "nobody saw it" are different properties; say which you mean.

Ask **once**, before the *soft* line — not before the hard one. Everything up to
and including `push main` is genuinely abandonable and needs no ceremony.

Then ask **once**. Not per channel — a prompt per step trains people to say yes.
Declining here is the dry run; there is no `--dry-run` flag because the preflight
always ran.

## Phase 5 · Execute — least permanent first

Order matters and is derived from reversibility, not convenience.

```
1  bump + tag + commit    ./scripts/bump-version.py minor|patch     (or --build-only)
                          git tag -d vX.Y.Z        ← it tagged PRE-bump HEAD
                          git add + git commit
                          git tag vX.Y.Z           ← now on the bump commit
                          verify: git rev-parse HEAD == git rev-parse vX.Y.Z^{}

2  push main (NOT tags)   git push origin main                      ~25 min for CI
                          release.yml fires on TAGS only — this publishes nothing.
                          Wait for green before spending the Mac lane.

3  Mac artefacts          SIGN_IDENTITY="Apple Distribution: Martin Storey (Z56GZVA2QB)" \
                            desktop/scripts/build-all.sh            ~35 min warm / ~50 cold
                          desktop/scripts/upload-testflight.sh      ← SOFT irreversible
                          desktop/scripts/build-dmg.sh              ~40 min, two notary waits
                          desktop/scripts/upload-dmg.sh             ← public permalink swaps

4  CLI publish            re-assert HEAD == tag == origin/main, then
                          → .claude/skills/new-release/SKILL.md Steps 5–6 ONLY
                            (push tag, PyPI verify, and its tag-surgery tree)
                                                                    ← HARD irreversible

5  website deploy         only AFTER PyPI confirms — see below
6  Snap                   gh workflow run snap.yml --ref main       (edge)
                          gh workflow run snap.yml --ref vX.Y.Z     (stable, Tier 2)
7  Tier 2 only            App Store submission, phased release on
```

**Step 1 owns the whole tag dance.** `bump-version.py` creates the tag on
*pre-bump* HEAD, before the commit exists, so it points at the wrong commit until
you delete and re-tag. Do that here, in one unit, and verify tag == HEAD before
moving on. Do **not** delegate this to `/new-release` Step 4: that step is the
same bump, and after step 1 the tree already satisfies its publish-pending case,
whose instruction is *"push the existing tag"* — which would push a tag pointing
at the pre-bump commit. Hand off Steps **5–6 only**.

**`SIGN_IDENTITY` is not optional.** Unset, it defaults to `-` (ad-hoc), and
`build-all.sh` then silently skips the identity check, the provisioning-profile
check and the notarytool check — six gates off, no warning, and you find out 35
minutes later at the upload. `build-dmg.sh` needs no such care: it defaults to
the Developer ID identity and refuses ad-hoc outright.

**Push `main` before the Mac lane, not after.** `release.yml` fires only on
`push: tags`, so pushing `main` publishes nothing anywhere — it just buys a CI
verdict before you spend 75 minutes and a permanently-consumed build number. The
old ordering conflated the two pushes and left the Mac lane running against code
CI had never seen. **Caveat worth stating out loud: one green is not proof on a
suite with a live flake, and the tag push re-runs CI, so a green now can still be
followed by a red then.** If that happens after the uploads, the release is
already partially published — the supersede path in `/new-release` Step 2 is the
answer, not a rerun.

**Budget cold, not warm.** A version bump invalidates the PyInstaller and
frontend caches, so the sidecar rebuild inside `build-all.sh` runs ~19 min rather
than ~6. A full Publish-tier release is **~2h15 wall-clock**, most of it waiting.

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
| Snap | `snap info bristlenose` (no `snap` on macOS — fall back to the workflow run's conclusion, and say that is what you did) |
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

Close with a table of what is now true per channel, plus the expiry clocks —
**`.dmg` 30 days from the *build*, TestFlight 90 from the *upload*.**

---

## Rules

- **Never bypass a script's internal gate.** If `check-pkg-shippable.sh` refuses,
  the answer is to fix the artefact, never to work around the check.
- **A partial release is a normal outcome**, not an error. PyPI can succeed while
  Homebrew's poll times out. Report per-channel truth, not one verdict.
- **Weekday releases land after 9pm London.** Weekends unrestricted. It is a
  guideline — confirm rather than refuse.
- **Every upload spends its build number forever.** A replacement needs
  `./scripts/bump-version.py --build-only`.
- **Do not author the changelog alone.** Draft it; the human decides what users
  are told. That is the whole point of the version being their call.
