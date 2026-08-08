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

**Two different acts. Establish which one this is, first:**

| | What it is | Version | Prose |
|---|---|---|---|
| **Release** | You are telling users something is different | bumps | required |
| **Rebuild** | Refreshing TestFlight/`.dmg` with nothing new to say — e.g. the 90-day expiry | `--build-only` | none |

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

**Mark the line where reversible becomes irreversible.** Everything before the
tag push can be abandoned; PyPI never can.

Then ask **once**. Not per channel — a prompt per step trains people to say yes.
Declining here is the dry run; there is no `--dry-run` flag because the preflight
always ran.

## Phase 5 · Execute — least permanent first

Order matters and is derived from reversibility, not convenience.

```
1  bump + commit          ./scripts/bump-version.py minor|patch     (or --build-only)
2  Mac artefacts          desktop/scripts/build-all.sh              ~35 min
                          desktop/scripts/upload-testflight.sh      gates internally
                          desktop/scripts/build-dmg.sh              ~40 min, two notary waits
                          desktop/scripts/upload-dmg.sh
3  CLI publish            → follow .claude/skills/new-release/SKILL.md Steps 4–6
                            (tag, push, PyPI verify, and its tag-surgery tree)
4  website deploy         only AFTER PyPI confirms — see below
5  Snap                   gh workflow run snap.yml --ref main       (edge)
                          gh workflow run snap.yml --ref vX.Y.Z     (stable, Tier 2)
6  Tier 2 only            App Store submission, phased release on
```

**Mac artefacts before the tag push.** A signing regression or expired profile
must surface while the version can still be abandoned. Push first and you have
burned an immutable PyPI version to learn it.

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
| Homebrew | the tap formula's `version` |
| TestFlight | `xcrun altool --build-status --delivery-id <uuid> …` |
| Snap | `snap info bristlenose` |
| `.dmg` | `curl -I` the versioned URL |

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
